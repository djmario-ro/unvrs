# Staff sign-in with Keycloak

Staging uses `https://keycloak.cloud.retreat480.com/realms/staging`, confidential
OIDC client `unvrs-staging`. Authentication belongs to Keycloak; UNVRS alone
assigns and checks [property-scoped staff roles](access-control.md). Guest QR/PIN and
device-key routes do not require staff sign-in.

The backend uses Authorization Code with PKCE S256, state, nonce, issuer,
audience and signature validation. The browser receives an opaque HttpOnly
session cookie. Refresh and ID tokens are encrypted in PostgreSQL using a key
derived from `SECRET_KEY`; access/refresh tokens are never exposed to frontend
JavaScript. Keep `SECRET_KEY` stable and backed up privately. Rotating it requires
users to sign in again. App sessions last at most `ACCESS_TOKEN_EXPIRE_HOURS`
(default 12 hours). Provider refresh checks happen at least every five minutes
on activity. Local account deletion, identity changes and token-version
revocation invalidate app access immediately. An IdP outage returns 503 when
revalidation is due; it does not grant access to an expired identity.

## Client configuration

Enable client authentication and standard authorization-code flow. Require PKCE
S256. Disable implicit flow, direct access grants and service accounts. Allow only:

- Redirect URI: `https://unvrs-staging.cloud.retreat480.com/api/v1/auth/oidc/callback`
- Post-logout URI: `https://unvrs-staging.cloud.retreat480.com/api/v1/auth/oidc/logged-out`
- Web origin: `https://unvrs-staging.cloud.retreat480.com`

Use the `profile` and `email` scopes. No realm/client roles grant UNVRS access.
Do not enable automatic registration or email-based account linking.

The backend Helm chart references runtime Secret `unvrs-oidc` containing
`OIDC_CLIENT_SECRET` and `OIDC_BOOTSTRAP_SUBJECT`. The latter explicitly links the
`ADMIN_USERNAME` row to that Keycloak user ID. Startup refuses to rebind an
existing identity and never restores a revoked membership. No OIDC secret belongs in Git or GitHub Actions.

## Add staff

1. Create the person in Keycloak's `staging` realm and set their credentials.
2. Copy their immutable Keycloak user ID (the OIDC `sub`).
3. In UNVRS Users, add a local username, that Keycloak user ID and the application
   roles. An existing identity can join another property using the same ID. Username/email
   similarity never links accounts automatically.

Changing a password, MFA or a sign-in policy happens in Keycloak. Changing access
or a role happens in UNVRS. Removing property access does not delete the person's Keycloak account or their
other memberships. Signing out revokes the local session and performs standard
Keycloak RP-initiated logout.

## Local development and rollback

Local development defaults to `AUTH_PROVIDER=local` and preserves password login.
To enable OIDC set `AUTH_PROVIDER=keycloak`, `OIDC_ISSUER`, `OIDC_CLIENT_ID`,
`OIDC_CLIENT_SECRET`, `OIDC_BOOTSTRAP_SUBJECT`, `FRONTEND_ORIGIN`, and a strong
`SECRET_KEY`. The production issuer must use HTTPS. The local callback origin
must be explicitly allowed in a separate development client.

For a provider-only rollback using the current property-aware application, set Helm `auth.provider=local` and redeploy with the
existing `ADMIN_USERNAME`/`ADMIN_PASSWORD` secret. Keycloak mode rejects the local
password endpoint and old local JWTs. External-only staff need local passwords
assigned before they can use local mode. The migration is additive; do not
reverse it while external-only accounts exist.

Publish chart changes from a feature branch. The trusted promotion workflow
updates chart versions in `main:gitops/staging`; Argo then synchronizes main.
Never edit `gitops/staging` on the feature branch.
