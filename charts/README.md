# Digest-locked UNVRS charts

Three independent OCI Helm charts are published to Harbor:
`unvrs-db`, `unvrs-backend` and `unvrs-frontend`, under
`oci://harbor.cloud.retreat480.com/unvrs`.

Every chart requires an image repository and SHA-256 digest. Its template
renders `repository@sha256:...`; there is no tag fallback. JSON schemas reject
missing/invalid digests and the old image.tag property. Backend/frontend use
multi-architecture image-index digests. PostgreSQL is pinned to the existing
16-alpine digest; dependency upgrades require a deliberate Git change.

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
substitution is needed. Automatic prune is disabled. DB PV/PVC also carry
Prune=false,Delete=false protections. Applications have no cascading deletion
finalizers. Existing Helm release records are retained for history but Helm
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

The existing PostgreSQL data remains on k8s-cs-worker02 at
`/var/lib/unvrs-staging/postgres`, on its retained local PV/PVC. Local storage
is node-bound and its declared 5Gi capacity is not a filesystem quota. No
replication or scheduled backups are provided by these charts. The initial
Compose database was not migrated.

Existing staging secrets required: `unvrs-db-credentials` (POSTGRES_DB,
POSTGRES_USER, POSTGRES_PASSWORD), `unvrs-backend-credentials` (DATABASE_URL,
SECRET_KEY), and `unvrs-staging-basic-auth` (htpasswd). Secrets remain externally
managed. The public frontend and API retain their staging Basic authentication.

Validate locally with `helm lint charts/db charts/backend charts/frontend`.
Package a release with `scripts/package-chart.py`; package only into an output
folder, not by modifying source values in place. `scripts/deploy-staging.sh`
now explains the GitOps promotion path instead of invoking Helm upgrades.

## CloudNativePG database

The db chart now provisions `Database` and `DatabaseRole` resources, not a PostgreSQL StatefulSet or PVC. Install it in namespace `postgres` alongside the existing `postgres-geo` CNPG Cluster. Its generated basic-auth credential Secret `unvrs-staging-db-credentials` is provisioned separately; never commit passwords. The application has a dedicated non-superuser role `unvrs_staging` and database `unvrs_staging`. Backend credentials point at `postgres-geo-rw.postgres.svc.cluster.local`, using TLS. Deleting the Helm resources retains the SQL database and role; deliberate destruction is a separate operation. The shared cluster controls digest-pinned images, storage, replication, and failover.

The October 2026 cutover intentionally discards the old standalone database and local PV data. Rolling back to an old db chart will recreate the obsolete StatefulSet; do not promote pre-CNPG charts as a rollback. The db Argo application targets `postgres`, while backend/frontend remain in `unvrs-staging`.
