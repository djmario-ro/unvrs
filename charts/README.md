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

Externally managed Secrets: `postgres/unvrs-staging-db-credentials` (basic-auth username/password for the CNPG role), `unvrs-staging/unvrs-backend-credentials` (DATABASE_URL and SECRET_KEY), `unvrs-staging/harbor-unvrs-pull`, and `unvrs-staging/unvrs-staging-basic-auth` (htpasswd). DATABASE_URL uses the dedicated role, the shared write service, database `unvrs_staging`, and `?ssl=require`; update both credential Secrets together on password rotation and restart the backend. Public staging Basic authentication remains enabled.

Validate locally with `helm lint charts/db charts/backend charts/frontend`.
Package a release with `scripts/package-chart.py`; package only into an output
folder, not by modifying source values in place. `scripts/deploy-staging.sh`
now explains the GitOps promotion path instead of invoking Helm upgrades.

## CloudNativePG database

The db chart now provisions `Database` and `DatabaseRole` resources, not a PostgreSQL StatefulSet or PVC. Install it in namespace `postgres` alongside the existing `postgres-geo` CNPG Cluster. Its generated basic-auth credential Secret `unvrs-staging-db-credentials` is provisioned separately; never commit passwords. The application has a dedicated non-superuser role `unvrs_staging` and database `unvrs_staging`. Backend credentials point at `postgres-geo-rw.postgres.svc.cluster.local`, using TLS. Deleting the Helm resources retains the SQL database and role; deliberate destruction is a separate operation. The shared cluster controls digest-pinned images, storage, replication, and failover.

The October 2026 cutover intentionally discards the old standalone database and local PV data. Rolling back to an old db chart will recreate the obsolete StatefulSet; do not promote pre-CNPG charts as a rollback. The db Argo application targets `postgres`, while backend/frontend remain in `unvrs-staging`.
