"""Exercise the real Authlib code/state/PKCE/JWKS verification, with a fake IdP."""
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import time
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

from authlib.integrations.starlette_client import OAuth
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import httpx
import jwt
import pytest
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.dependencies import COOKIE_NAME
from app.models.oidc_session import OIDCSession
from app.models.user import User
from app.utils import oidc


class Provider:
    issuer = "https://identity.example.test/realms/staging"
    subject = None
    nonce = None
    challenge = None
    token_calls = 0
    refresh_calls = 0
    revoked = False
    unavailable = False
    claim_changes = None
    bad_signature = False

    def __init__(self):
        self.subject = str(uuid4())
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        self.public.update(kid="test-key", alg="RS256", use="sig")
        self.metadata = {"issuer": self.issuer, "authorization_endpoint": self.issuer + "/auth",
                         "token_endpoint": self.issuer + "/token", "jwks_uri": self.issuer + "/certs",
                         "end_session_endpoint": self.issuer + "/logout",
                         "id_token_signing_alg_values_supported": ["RS256"]}
        registry = OAuth()
        self.client = registry.register("keycloak", client_id="unvrs-test", client_secret="test-client-secret",
            server_metadata_url=self.issuer + "/.well-known/openid-configuration",
            client_kwargs={"scope": "openid profile email", "code_challenge_method": "S256",
                           "token_endpoint_auth_method": "client_secret_basic",
                           "transport": httpx.MockTransport(self.handle)})

    def token(self):
        now = int(time.time())
        access = "opaque-provider-access-token"
        claims = {"iss": self.issuer, "aud": "unvrs-test", "sub": self.subject,
                  "exp": now + 300, "iat": now, "nonce": self.nonce,
                  "preferred_username": "admin", "realm_access": {"roles": ["admin"]},
                  "at_hash": base64.urlsafe_b64encode(hashlib.sha256(access.encode()).digest()[:16]).decode().rstrip("=")}
        claims.update(self.claim_changes or {})
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048) if self.bad_signature else self.key
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        return {"access_token": access, "refresh_token": "provider-refresh-token-" + self.subject,
                "id_token": jwt.encode(claims, pem, algorithm="RS256", headers={"kid": "test-key"}),
                "token_type": "Bearer", "expires_in": 300}

    def handle(self, request):
        path = request.url.path
        if path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(200, json=self.metadata)
        if path.endswith("/certs"):
            return httpx.Response(200, json={"keys": [self.public]})
        if path.endswith("/token"):
            self.token_calls += 1
            if self.unavailable:
                raise httpx.ConnectError("Identity service unavailable", request=request)
            params = parse_qs(request.content.decode())
            assert request.headers["authorization"] == "Basic " + base64.b64encode(b"unvrs-test:test-client-secret").decode()
            if params["grant_type"] == ["authorization_code"]:
                verifier = params["code_verifier"][0]
                assert base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=") == self.challenge
            else:
                assert params["grant_type"] == ["refresh_token"]
                self.refresh_calls += 1
                if self.revoked:
                    return httpx.Response(400, json={"error": "invalid_grant"})
            return httpx.Response(200, json=self.token())
        raise AssertionError(str(request.url))


@pytest.fixture
async def provider(monkeypatch):
    provider = Provider()
    monkeypatch.setattr(settings, "auth_provider", "keycloak")
    monkeypatch.setattr(settings, "oidc_issuer", provider.issuer)
    monkeypatch.setattr(settings, "oidc_client_id", "unvrs-test")
    monkeypatch.setattr(settings, "oidc_client_secret", "test-client-secret")
    monkeypatch.setattr(settings, "frontend_origin", "http://test")
    monkeypatch.setattr(oidc, "client", lambda: provider.client)
    return provider


async def mapped_user(provider, role="frontdesk"):
    async with AsyncSessionLocal() as db:
        user = User(username="federated-" + uuid4().hex[:12], password_hash=None,
                    oidc_issuer=provider.issuer, oidc_subject=provider.subject, role=role)
        db.add(user)
        await db.commit()
        return user.id


async def begin(anon, provider):
    response = await anon.get("/api/v1/auth/oidc/login")
    assert response.status_code == 302
    params = parse_qs(urlsplit(response.headers["location"]).query)
    assert params["response_type"] == ["code"]
    assert params["code_challenge_method"] == ["S256"]
    assert "client_secret" not in params
    provider.nonce = params["nonce"][0]
    provider.challenge = params["code_challenge"][0]
    return params["state"][0]


async def complete(anon, provider):
    state = await begin(anon, provider)
    return await anon.get("/api/v1/auth/oidc/callback?" + urlencode({"state": state, "code": "test-code"}))


async def test_oidc_uses_local_permissions_and_hides_provider_tokens(anon, provider):
    await mapped_user(provider)
    response = await complete(anon, provider)
    assert response.status_code == 303
    assert response.headers["location"] == "http://test/app"
    cookie = anon.cookies[COOKIE_NAME]
    assert cookie.startswith("oidc.")
    assert "provider-refresh-token" not in str(anon.cookies)
    assert "opaque-provider-access-token" not in str(anon.cookies)
    assert "HttpOnly" in response.headers["set-cookie"]
    me = await anon.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["role"] == "frontdesk"
    # The signed ID token claims preferred_username=admin and a realm admin role;
    # neither can grant UNVRS administrator access.
    assert (await anon.get("/api/v1/users")).status_code == 403
    async with AsyncSessionLocal() as db:
        session = await db.get(OIDCSession, oidc.token_hash(cookie))
        assert session.refresh_token != "provider-refresh-token-" + provider.subject
        assert oidc.cipher().decrypt(session.refresh_token.encode()).decode().startswith("provider-refresh-token")


async def test_unmapped_identity_cannot_claim_existing_admin_by_username(anon, provider):
    response = await complete(anon, provider)
    assert response.headers["location"].endswith("error=access_denied")
    assert COOKIE_NAME not in anon.cookies
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
        assert user.oidc_subject is None


async def test_state_mismatch_is_rejected_before_code_exchange(anon, provider):
    await begin(anon, provider)
    response = await anon.get("/api/v1/auth/oidc/callback?state=wrong&code=test-code")
    assert response.headers["location"].endswith("error=oidc_failed")
    assert provider.token_calls == 0


@pytest.mark.parametrize("changes", [{"nonce": "wrong"}, {"iss": "https://other.test/realms/staging"},
                                  {"aud": "other-client"}, {"exp": 1}])
async def test_invalid_id_token_claims_are_rejected(anon, provider, changes):
    await mapped_user(provider)
    state = await begin(anon, provider)
    provider.claim_changes = changes
    response = await anon.get("/api/v1/auth/oidc/callback?" + urlencode({"state": state, "code": "test-code"}))
    assert response.headers["location"].endswith("error=oidc_failed")
    assert COOKIE_NAME not in anon.cookies


async def test_forged_signature_is_rejected(anon, provider):
    await mapped_user(provider)
    provider.bad_signature = True
    response = await complete(anon, provider)
    assert response.headers["location"].endswith("error=oidc_failed")
    assert COOKIE_NAME not in anon.cookies


async def test_local_password_login_and_local_jwt_are_disabled_in_oidc_mode(anon, provider):
    from app.utils.auth import create_access_token
    response = await anon.post("/api/v1/auth/login", json={"username":"admin", "password":"test-admin-password"})
    assert response.status_code == 409
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
        token = create_access_token(user.id, user.token_version)
    anon.cookies.set(COOKIE_NAME, token)
    assert (await anon.get("/api/v1/auth/me")).status_code == 401


async def expire_provider_session(anon):
    async with AsyncSessionLocal() as db:
        session = await db.get(OIDCSession, oidc.token_hash(anon.cookies[COOKIE_NAME]))
        session.provider_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.commit()


async def test_refresh_revalidates_identity_and_disabled_users_lose_access(anon, provider):
    await mapped_user(provider)
    await complete(anon, provider)
    await expire_provider_session(anon)
    assert (await anon.get("/api/v1/auth/me")).status_code == 200
    assert provider.refresh_calls == 1
    await expire_provider_session(anon)
    provider.revoked = True
    assert (await anon.get("/api/v1/auth/me")).status_code == 401
    async with AsyncSessionLocal() as db:
        assert await db.get(OIDCSession, oidc.token_hash(anon.cookies[COOKIE_NAME])) is None


async def test_provider_outage_fails_closed_without_deleting_session(anon, provider):
    await mapped_user(provider)
    await complete(anon, provider)
    await expire_provider_session(anon)
    provider.unavailable = True
    assert (await anon.get("/api/v1/auth/me")).status_code == 503
    async with AsyncSessionLocal() as db:
        assert await db.get(OIDCSession, oidc.token_hash(anon.cookies[COOKIE_NAME])) is not None


async def test_refresh_is_persisted_even_when_application_authorization_denies(anon, provider):
    await mapped_user(provider, "frontdesk")
    await complete(anon, provider)
    await expire_provider_session(anon)
    assert (await anon.get("/api/v1/users")).status_code == 403
    async with AsyncSessionLocal() as db:
        session = await db.get(OIDCSession, oidc.token_hash(anon.cookies[COOKIE_NAME]))
        assert session.provider_expires_at > datetime.now(timezone.utc)
    assert (await anon.get("/api/v1/auth/me")).status_code == 200
    assert provider.refresh_calls == 1


async def test_role_changes_and_revocation_are_local_and_immediate(anon, provider):
    uid = await mapped_user(provider, "admin")
    await complete(anon, provider)
    assert (await anon.get("/api/v1/users")).status_code == 200
    async with AsyncSessionLocal() as db:
        user = await db.get(User, uid)
        user.role = "frontdesk"
        await db.commit()
    assert (await anon.get("/api/v1/users")).status_code == 403
    async with AsyncSessionLocal() as db:
        await db.delete(await db.get(User, uid))
        await db.commit()
    assert (await anon.get("/api/v1/auth/me")).status_code == 401


async def test_logout_revokes_local_session_and_checks_provider_callback_state(anon, provider):
    await mapped_user(provider)
    await complete(anon, provider)
    cookie = anon.cookies[COOKIE_NAME]
    response = await anon.post("/api/v1/auth/logout", headers={"Origin":"http://test"})
    assert response.status_code == 200
    params = parse_qs(urlsplit(response.json()["logout_url"]).query)
    assert params["post_logout_redirect_uri"] == ["http://test/api/v1/auth/oidc/logged-out"]
    assert "id_token_hint" in params and "state" in params
    async with AsyncSessionLocal() as db:
        assert await db.get(OIDCSession, oidc.token_hash(cookie)) is None
    assert (await anon.get("/api/v1/auth/me")).status_code == 401
    response = await anon.get("/api/v1/auth/oidc/logged-out?state="+params["state"][0])
    assert response.headers["location"] == "http://test/login"


async def test_cross_origin_logout_does_not_revoke_session(anon, provider):
    await mapped_user(provider)
    await complete(anon, provider)
    assert (await anon.post("/api/v1/auth/logout", headers={"Origin":"https://evil.test"})).status_code == 403
    assert (await anon.get("/api/v1/auth/me")).status_code == 200


async def test_oidc_user_management_never_accepts_passwords(anon, provider):
    await mapped_user(provider, "admin")
    await complete(anon, provider)
    response = await anon.post("/api/v1/users", json={"username":"external-"+uuid4().hex[:10],"password":"should-not-be-stored"})
    assert response.status_code == 400
    response = await anon.post("/api/v1/users", json={"username":"external-"+uuid4().hex[:10],"oidc_subject":str(uuid4()),"role":"frontdesk"})
    assert response.status_code == 201 and response.json()["oidc_subject"]


async def test_guest_room_routes_remain_public_with_oidc_enabled(anon, provider):
    from app.models.guest import Guest
    from app.models.guest_room import GuestRoom
    from app.models.room import Room
    async with AsyncSessionLocal() as db:
        guest = Guest(firstname="OIDC", lastname="Guest")
        room = Room(name="OIDC-" + uuid4().hex[:12])
        db.add_all([guest, room])
        await db.flush()
        db.add(GuestRoom(guest_id=guest.id, room_id=room.id, pin="123456",
                         check_out=datetime.now(timezone.utc) + timedelta(days=1)))
        await db.commit()
        public_id = room.public_id
    assert COOKIE_NAME not in anon.cookies
    response = await anon.post(f"/api/v1/door/{public_id}/session", json={"pin":"123456"})
    assert response.status_code == 200
    assert (await anon.get(f"/api/v1/door/{public_id}/session")).status_code == 200
    assert (await anon.get("/api/v1/auth/me")).status_code == 401
