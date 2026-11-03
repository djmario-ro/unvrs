from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.property import PropertyMembership
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.utils import audit as audit_log
from app.utils.auth import hash_password

router = APIRouter(
    prefix="/users", tags=["users"], dependencies=[Depends(require_admin)]
)


def check_grant(
    current: User, roles: list[str], previous: tuple[str, ...] | list[str] = ()
):
    if "owner" not in current.roles and (
        {"owner", "administrator"} & (set(roles) | set(previous))
    ):
        raise HTTPException(
            403, "Only an owner can manage owner or administrator access"
        )


@router.get("", response_model=list[UserRead])
async def list_users(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    rows = (
        await db.execute(
            select(User, PropertyMembership)
            .join(PropertyMembership, PropertyMembership.user_id == User.id)
            .where(PropertyMembership.property_id == current.active_property_id)
            .order_by(User.id)
        )
    ).all()
    # Build response objects now: the current identity may also appear in this
    # list and its request-local permission context must not be mutated.
    return [
        UserRead.model_validate(expose_copy(user, membership))
        for user, membership in rows
    ]


def expose_copy(user, membership):
    from types import SimpleNamespace

    return SimpleNamespace(
        id=user.id,
        username=user.username,
        effective_role=next(
            role
            for role in (
                "owner",
                "administrator",
                "frontdesk",
                "housekeeping",
                "maintenance",
            )
            if role in membership.roles
        ),
        roles=membership.roles,
        active_property_id=membership.property_id,
        properties=[],
        oidc_subject=user.oidc_subject,
        created_at=user.created_at,
    )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    roles = body.assigned_roles()
    check_grant(current, roles)
    if settings.auth_provider == "keycloak":
        if body.password is not None:
            raise HTTPException(400, "Passwords are managed in Keycloak")
        if not body.oidc_subject:
            raise HTTPException(422, "Keycloak user ID is required to grant access")
        user = (
            await db.execute(
                select(User).where(
                    User.oidc_issuer == settings.oidc_issuer.rstrip("/"),
                    User.oidc_subject == body.oidc_subject,
                )
            )
        ).scalar_one_or_none()
        # An existing global identity may join another property. Neither its
        # username nor its other memberships are changed by this operation.
        if user is None:
            if await db.scalar(select(User.id).where(User.username == body.username)):
                raise HTTPException(409, "Username already exists")
            user = User(
                username=body.username,
                password_hash=None,
                oidc_issuer=settings.oidc_issuer.rstrip("/"),
                oidc_subject=body.oidc_subject,
                role="frontdesk",
            )
            db.add(user)
            await db.flush()
    else:
        if not body.password:
            raise HTTPException(422, "Password is required for local accounts")
        if body.oidc_subject:
            raise HTTPException(400, "Federated access is not enabled")
        if await db.scalar(select(User.id).where(User.username == body.username)):
            raise HTTPException(409, "Username already exists")
        user = User(
            username=body.username,
            password_hash=hash_password(body.password),
            role="frontdesk",
        )
        db.add(user)
        await db.flush()
    if await db.get(PropertyMembership, (user.id, current.active_property_id)):
        raise HTTPException(409, "This identity already has access to this property")
    membership = PropertyMembership(
        user_id=user.id, property_id=current.active_property_id, roles=roles
    )
    db.add(membership)
    await audit_log.log(
        db,
        "user.create",
        f"Granted property access to user id={user.id}: {','.join(roles)}",
    )
    await db.flush()
    return expose_copy(user, membership)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    body: UserUpdate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await db.get(PropertyMembership, (user_id, current.active_property_id))
    user = await db.get(User, user_id) if membership else None
    if not user:
        raise HTTPException(404, "User not found in this property")
    if settings.auth_provider == "local" and user.username == settings.admin_username:
        raise HTTPException(
            400,
            "This account is managed by ADMIN_USERNAME and the server bootstrap mapping",
        )
    if user_id == current.id:
        raise HTTPException(400, "You cannot change your own role or sign-in identity")
    roles = (
        body.assigned_roles()
        if body.roles is not None or body.role is not None
        else membership.roles
    )
    check_grant(current, roles, membership.roles)
    if body.oidc_subject is not None and body.oidc_subject != user.oidc_subject:
        memberships = (
            await db.scalars(
                select(PropertyMembership).where(PropertyMembership.user_id == user.id)
            )
        ).all()
        if (
            settings.auth_provider != "keycloak"
            or user.oidc_subject is not None
            or len(memberships) != 1
        ):
            raise HTTPException(
                400,
                "Sign-in identity cannot be rebound; remove this membership and invite the correct Keycloak identity",
            )
        duplicate = await db.scalar(
            select(User.id).where(
                User.oidc_issuer == settings.oidc_issuer.rstrip("/"),
                User.oidc_subject == body.oidc_subject,
            )
        )
        if duplicate:
            raise HTTPException(
                409, "This identity already exists; invite it to the property instead"
            )
        # A legacy local account can be linked for the first time only if its
        # entire access belongs to this property. Existing global identities
        # cannot be changed through a tenant administrator.
        user.oidc_issuer = settings.oidc_issuer.rstrip("/")
        user.oidc_subject = body.oidc_subject
        user.password_hash = None
        user.token_version += 1
    if body.password:
        if settings.auth_provider != "local":
            raise HTTPException(400, "Passwords are managed in Keycloak")
        if (
            len(
                (
                    await db.scalars(
                        select(PropertyMembership).where(
                            PropertyMembership.user_id == user.id
                        )
                    )
                ).all()
            )
            > 1
        ):
            raise HTTPException(
                400,
                "Shared-account passwords cannot be changed by a property administrator",
            )
        user.password_hash = hash_password(body.password)
        user.token_version += 1
    membership.roles = roles
    await audit_log.log(
        db,
        "user.update",
        f"Updated property access for user id={user_id}: {','.join(roles)}",
    )
    await db.flush()
    return expose_copy(user, membership)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user_id == current.id:
        raise HTTPException(400, "You cannot delete your own account")
    membership = await db.get(PropertyMembership, (user_id, current.active_property_id))
    if not membership:
        raise HTTPException(404, "User not found in this property")
    user = await db.get(User, user_id)
    if settings.auth_provider == "local" and user.username == settings.admin_username:
        raise HTTPException(
            400,
            "This account is managed by ADMIN_USERNAME and the server bootstrap mapping",
        )
    check_grant(current, [], membership.roles)
    await db.delete(membership)
    await audit_log.log(
        db, "user.delete", f"Removed property access for user id={user_id}"
    )
