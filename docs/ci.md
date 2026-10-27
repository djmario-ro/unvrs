# Container image CI

GitHub Actions workflow: `.github/workflows/images.yml`.
The public repository uses standard GitHub-hosted Ubuntu 24.04 runners.

Pull requests to `main` build the frontend and backend for linux/amd64 and
linux/arm64, without registry login or publishing. The frontend build runs
TypeScript checking and Vite compilation. Backend builds install its pinned
Python dependencies; application integration tests are not part of this workflow.

Pushes to `main` publish both images to the private Harbor project `unvrs`:

- `harbor.cloud.retreat480.com/unvrs/frontend:sha-<full-git-sha>`
- `harbor.cloud.retreat480.com/unvrs/backend:sha-<full-git-sha>`

The `staging` tag also tracks main builds. Version tags such as `v1.0.0` add
the corresponding image tag. Manual workflow runs publish commit tags; they
update `staging` only when dispatched on main. Run summaries contain the image
tags and manifest digest. Prefer commit tags or digests for deployments.

Two repository Actions secrets are required:

- `HARBOR_USERNAME`
- `HARBOR_PASSWORD`

They belong to Harbor robot account `robot$unvrs+github-actions-unvrs`, which has
only repository pull and push permissions within the private `unvrs` project.
It has a one-year expiry; rotate the robot secret and update the GitHub secret
before expiry. Harbor remains behind its public trusted HTTPS endpoint so
GitHub-hosted runners can reach it without VPN access.

Actions are pinned to commit hashes. Registry credentials are not passed to
pull-request builds, and no pull_request_target workflow is used. The checkout
step does not persist GitHub credentials. Build caches use GitHub Actions cache
storage independently for frontend and backend.

Chart publication does not itself promote staging; an explicit chart-version
commit in gitops/staging drives Argo CD.

Frontend Docker builds use the committed package-lock.json with npm ci.
Both application contexts exclude local secrets, dependencies and build outputs
using .dockerignore files.

## Digest-locked Helm publishing

The workflow now also publishes `unvrs-frontend`, `unvrs-backend`, and `unvrs-db`
OCI charts to Harbor. Application chart defaults contain each build's exact
multi-architecture image-index digest. The database chart declares Database and DatabaseRole resources on the existing
CloudNativePG cluster; PostgreSQL images are pinned by that infrastructure Cluster. Published chart versions are
`0.1.0-ci.RUN_NUMBER.RUN_ATTEMPT`; appVersion records the source commit.

Images additionally get unique `build-RUN_ID-RUN_ATTEMPT` tags, which keep
older image digests referenced even when staging or commit tags move.
Chart repository versions are immutable in Harbor. No automatic image retention
policy is enabled; preserve all image indexes referenced by retained releases.

Pull requests lint schemas and charts but do not publish. Chart publishing
uses the existing CI pull/push robot. Argo CD and Kubernetes have separate
pull-only robots. See charts/README.md for explicit Git-based promotion.
GitOps-only and documentation commits do not trigger another image build.
