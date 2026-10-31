# Digest-locked UNVRS charts

Three independent OCI Helm charts are published to Harbor:
`unvrs-db`, `unvrs-backend` and `unvrs-frontend`, under
`oci://harbor.cloud.retreat480.com/unvrs`.

Application charts require an image repository and SHA-256 digest. Each template
renders `repository@sha256:...`; there is no tag fallback. JSON schemas reject
missing/invalid digests and the old image.tag property. Backend/frontend use
multi-architecture image-index digests. PostgreSQL images are pinned by the shared CloudNativePG Cluster, outside these application charts.

CI packages a copy of each application chart with the exact digest emitted
by that build. Chart versions are `0.1.0-ci.RUN_NUMBER.RUN_ATTEMPT` and appVersion
records the source commit. Source defaults are valid bootstrap digests;
published application chart defaults are replaced with that build's digest.
Harbor enforces immutable versions for chart repositories named `unvrs-*`.
Build-specific image tags preserve references independently of moving staging tags.
No automatic Harbor retention policy is configured. Any future retention rule
must preserve image indexes and their child manifests needed by retained charts.

## Staging delivery

Argo CD fetches charts with a project-scoped pull-only account. Worker nodes
use a separate pull-only account via `unvrs-staging/harbor-unvrs-pull`.
Both credentials live in Kubernetes Secrets; none are committed to Git.

`gitops/bootstrap.yaml` creates the restricted staging AppProject and root
Application. The root watches `gitops/staging` on GitHub main. Three child
Applications select exact OCI chart versions and preserve original release names.
Their default values already contain the image locks; no runtime image-tag
substitution is needed. Automatic prune is disabled. Database and role reclaim policies retain SQL objects. Applications have no cascading deletion
finalizers. Backend/frontend Helm release records are retained for history but Helm
must not independently upgrade these now Argo-managed resources.

After a successful publish of all three charts, promote explicitly:

```sh
python3 scripts/promote-staging.py 0.1.0-ci.RUN_NUMBER.RUN_ATTEMPT
git diff -- gitops/staging
# Commit and push these manifest changes after review.
```

Argo CD reconciles the promotion commit. Reverting the version commit restores
the older charts and their pinned images; database data/schema compatibility
still needs consideration when rolling back application/database versions.
Do not rerun only failed jobs and assume a complete three-chart release exists
under the new attempt number; rerun all jobs for a coherent release version.

## Database and secrets

UNVRS uses the shared three-instance `postgres/postgres-geo` CloudNativePG cluster with asynchronous replication between Sasca and Timișoara. The db chart creates its own `unvrs_staging` database and login. The legacy standalone database and its local data were deleted during cutover. Backup/PITR storage is still not configured.

Externally managed Secrets: `postgres/unvrs-staging-db-credentials` (basic-auth username/password for the CNPG role), `unvrs-staging/unvrs-backend-credentials` (DATABASE_URL and SECRET_KEY), `unvrs-staging/harbor-unvrs-pull`, and `unvrs-staging/homeassistant-api` (HA_TOKEN). DATABASE_URL uses the dedicated role, the shared write service, database `unvrs_staging`, and `?ssl=require`; update both credential Secrets together on password rotation and restart the backend. HTTP Basic authentication is disabled (`auth.enabled: false`). The application session protects staff APIs; guest door pages and PIN validation are public.

Validate locally with `helm lint charts/db charts/backend charts/frontend`.
Package a release with `scripts/package-chart.py`; package only into an output
folder, not by modifying source values in place. `scripts/deploy-staging.sh`
now explains the GitOps promotion path instead of invoking Helm upgrades.

## Staff application rollout

The application now uses Alembic instead of creating tables on startup. The
backend chart runs a digest-locked migration Job as an Argo CD PreSync hook
(or Helm pre-install/pre-upgrade hook). A failed migration blocks rollout.
Apply `gitops/bootstrap.yaml` before the first promotion to grant the staging
AppProject permission to manage Jobs. Subsequent deploys migrate automatically;
do not run the reset script during ordinary promotions.

Keep `DATABASE_URL` and `SECRET_KEY` in `unvrs-backend-credentials`. Add a strong
`ADMIN_PASSWORD` and optionally `ADMIN_USERNAME` (default `admin`). The configured
admin is reconciled on startup; changing its password revokes previous sessions.
The chart retains HTTPS cookies and the staging origin. Staff use application
login; the master admin credentials come from the backend Secret. HTTP Basic
is disabled so printed room QR links work without any staff login.
Staff sign in at `/login`, then use `/app`; old `/admin` links redirect there.
Room photos are stored in PostgreSQL. The Helm Nginx config allows 6 MB requests
while the API enforces a 5 MB image limit.

### One-time reset from v1 (existing UNVRS data is discarded)

Wait for the new main-branch CI run to publish all three charts successfully.
Record its chart version and backend image digest. The old v1 schema is not an
Alembic baseline: do not stamp it or run the initial migrations over it.

1. Apply `kubectl apply -f gitops/bootstrap.yaml` to allow migration Jobs.
2. Temporarily remove `spec.syncPolicy.automated` from both
   `argocd/unvrs-staging-root` and `argocd/unvrs-backend` Applications, in that
   order. Confirm neither has a sync operation in progress. This prevents
   reconciliation from restarting the old backend while the schema is reset.
3. While the root is paused, commit and push the new versions with
   `scripts/promote-staging.py VERSION`. Pin the paused root Application's
   `spec.source.targetRevision` to the full 40-character promotion commit SHA.
   This prevents cached resolution of `main` from restarting the old backend.
4. Scale `unvrs-staging/unvrs-backend` to zero and wait for its pods to terminate.
   Run the guarded reset, using the newly published backend digest:

   ```sh
   python3 scripts/reset-staging-db.py --context sasca \
     --image harbor.cloud.retreat480.com/unvrs/backend@sha256:NEW_DIGEST \
     --confirm-reset unvrs_staging
   ```

   It validates the database, role, shared CNPG host, and required TLS setting
   before dropping/recreating only `unvrs_staging.public`. It uses the existing
   application Secret and never deletes the CNPG cluster, database, or role.
5. Re-enable automatic sync on the root while keeping its source pinned to
   that exact commit. The root restores child automatic sync from Git; the
   backend PreSync Job applies migrations before the Deployment starts.
6. Confirm all three Applications are Synced/Healthy at the new chart version,
   the backend actually runs the published image with one available replica,
   and staff login, room/photo creation, bookings, and door PIN validation work.
   Delete the completed `unvrs-schema-reset-*` Jobs after verification.
7. Pause root automatic sync again, change its source back to `main`, and request
   a hard refresh. Wait until `status.sync.revision` resolves to the promotion
   commit or a verified newer commit containing the same release versions.
   Only then reapply `gitops/bootstrap.yaml` to restore normal automatic tracking.
   Do not rely on Synced/Healthy alone: manifest-fetch errors and stale status
   can mask a stopped backend. Inspect Application conditions and pod images.

After this destructive cutover, do not promote v1 application charts against the
new schema. A return to v1 requires another deliberate schema reset.

### Messaging

WhatsApp source is retained in `whatsapp/`, but the current three-chart pipeline
does not build or deploy it. Leave `WHATSAPP_SERVICE_URL` and `SMS_GATEWAY_URL`
unset for the initial rollout: deliveries are recorded as `mocked`, not sent.
Deploying WhatsApp later needs its own image/chart, internal Service, persistent
linked-device session storage, and matching `WHATSAPP_API_TOKEN`/`API_TOKEN`
Secrets. Do not use the friend's Coolify Compose stack for cluster deployment.

### Guest keys and Home Assistant doors

Set **Home Assistant entity ID** in the admin room editor: `lock.room_101`
uses `/api/services/lock/unlock` with `{"entity_id":"lock.room_101"}`.
`script.open_door` remains supported for an existing timed opening script.
Blank disables opening for that room. The backend selects the entity from the
room record; guest requests cannot supply an actuator. Renaming a room does not
change its physical target. Duplicating a room clears the copied actuator field.

The token stays in `unvrs-staging/homeassistant-api`, key `HA_TOKEN`, and is
injected only into the backend. The browser never receives it. The schema
upgrade copies the old `homeAssistant.doorScripts` chart mapping into matching
room records once. The migration Job receives that legacy mapping; running
backends read the editable database field, not the chart map. No reset is needed.

A guest scans the same permanent room QR and enters the reusable stay PIN on
each phone. This creates a distinct random, HttpOnly, Secure, SameSite=Strict
cookie scoped to that room's door API. Only its SHA-256 hash is stored in the
database. PIN activation never opens a door or marks check-in. Reloading the
room page restores the slider without entering the PIN again.

Each completed slide is a JSON POST. It rechecks device revocation/expiry, the
stay's current dates, room binding, and key version before calling Home
Assistant. Origin validation and Strict cookies protect against cross-site
requests. GETs, partial drags, track taps, invalid/revoked keys, and expired stays
never open hardware. Keyboard slider completion is supported. Successful
opening marks check-in; failures return 503 without marking arrival or showing
success. There are no automatic retries after ambiguous actuator failures.

The cookie expires at the known checkout time (30 days for open-ended bookings).
If checkout is extended beyond a previously issued cookie's expiry, the guest
can activate again with the stay PIN. Phones for different rooms have separate
cookie paths; guest sessions do not authorize staff APIs.

In **Bookings → Guest devices and access**, staff can revoke one phone, disable
all access for a stay, or replace the PIN. Disabling access blocks both existing
sessions and PIN activation until a replacement PIN is generated. Replacing a
PIN or reassigning a room invalidates previously activated devices; deleting a
booking removes its device keys. Date changes take effect on the next request.
A single-device revocation does not prevent reactivation by someone who still
knows the shared PIN; replace the PIN to stop that too. Guests can also select
**Forget this device**, revoking that phone's key on the server.

## CloudNativePG database

The db chart now provisions `Database` and `DatabaseRole` resources, not a PostgreSQL StatefulSet or PVC. Install it in namespace `postgres` alongside the existing `postgres-geo` CNPG Cluster. Its generated basic-auth credential Secret `unvrs-staging-db-credentials` is provisioned separately; never commit passwords. The application has a dedicated non-superuser role `unvrs_staging` and database `unvrs_staging`. Backend credentials point at `postgres-geo-rw.postgres.svc.cluster.local`, using TLS. Deleting the Helm resources retains the SQL database and role; deliberate destruction is a separate operation. The shared cluster controls digest-pinned images, storage, replication, and failover.

The October 2026 cutover intentionally discards the old standalone database and local PV data. Rolling back to an old db chart will recreate the obsolete StatefulSet; do not promote pre-CNPG charts as a rollback. The db Argo application targets `postgres`, while backend/frontend remain in `unvrs-staging`.
