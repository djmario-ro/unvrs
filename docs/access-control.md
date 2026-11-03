# Property access and staff roles

Keycloak authenticates people. UNVRS identifies them by the immutable
`oidc_issuer` + `oidc_subject` pair and stores their property memberships locally.
Usernames and email addresses are display/contact information, not identity keys.
Renaming a Keycloak user does not alter their identity. Replacing an account with
a new Keycloak user requires explicitly inviting the new subject.

A person can have several memberships and several roles in each membership:

- **Owner**: all property operations, staff access, and property creation. Only
  owners can grant, change or remove owner/administrator memberships.
- **Administrator**: reception, rooms, audit, messaging, housekeeping,
  maintenance, and access management for operational staff.
- **Frontdesk**: dashboard, guests, bookings, room information and guest access.
- **Housekeeping**: room status without guest identities/PINs, cleaning
  confirmations, and maintenance issue reporting.
- **Maintenance**: room status without guest identities/PINs, issue reporting,
  and ticket status changes (`open`, `in_progress`, `resolved`).

Roles are additive. Housekeeping + Maintenance gives both operational pages,
without reception or administration. Staff cannot change their own access.
Removing a membership does not delete the person's Keycloak account, global
UNVRS identity, or access to other properties. Permission changes are checked on
every API request and do not require another login. Initial bootstrap access is
not restored on restart after an owner revokes it.

## Staff access screen

Choose the property in the sidebar, then open **Staff access** as an owner or
administrator. Add the Keycloak user ID and select one or more roles. To grant
an existing person access to another property, use the same subject; UNVRS reuses
the identity and creates another membership. Identity rebinding is deliberately
not a property-level edit, since it could change another tenant's person.
Remove the membership and invite the correct identity instead. Legacy local
accounts can be linked for the first time through Edit only if they belong
exclusively to this property.

The API accepts `roles: ["housekeeping", "maintenance"]`. The old singular
`role` request remains compatible (`admin` means `administrator`), but
permissions never use the legacy global `users.role` column. Responses include
`roles`, the selected `property_id`, and the signed-in person's accessible
`properties`. Other staff listings disclose only the selected property's access.

## Property isolation

The browser sends `X-Property-ID` for the selected property. The backend checks
membership before using that value; changing the header cannot grant access.
Authenticated ORM queries, ID lookups and relationship loads are scoped to the
validated property. Writes use the same scope. Composite database foreign keys
also reject assignments/images/devices/tickets linked across properties. Room
names and guest emails are unique within a property rather than globally.

The migration moves existing data into **Retreat 480** and converts existing
admin/frontdesk roles into memberships. It preserves bookings, PINs, device keys
and history. Unknown-identity authentication failures remain platform security
audit events, not another tenant's activity. Public guest routes use the
room-scoped guest capability and stay independent from staff authentication.

Owners can create another property and switch between memberships. Existing
Home Assistant and messaging runtime secrets belong to the original property;
new properties cannot invoke these shared integrations. Provisioning separate
integration credentials per property is a later operator/configuration step.
No Keycloak roles or service-account administrative privileges are needed.

## Delivery and rollback

Deploy through feature CI -> Harbor -> promotion into `main:gitops/staging` ->
Argo. The schema upgrade is tested both fresh and with pre-existing data.
The old global role column is retained for transition only. Do not roll back to
images that predate property authorization after adding another property: they
cannot enforce tenant isolation. The migration refuses a destructive downgrade.
