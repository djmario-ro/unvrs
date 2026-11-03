# UNVRS CI/CD

Argo CD watches **main:gitops/staging**. Development branches (not only a hardcoded
feature name) build and publish; main and reserved `gitops/*` branches do not.
After all tests and publishers pass, trusted main-branch logic automatically
updates the three chart versions on main. No application code is merged by the
promotion bot.

Read [the shared delivery policy](staging-delivery.md) for the complete feature →
Harbor → main → Argo CD flow, PR guard, race protection and reruns.

## Validation and publication

CI runs the backend integration suite against a disposable PostgreSQL service,
frontend TypeScript/Vite build and delivery-policy tests before publishing.
PR builds lint and build without registry credentials or publishing.

Images `unvrs/backend` and `unvrs/frontend` are built for AMD64 and ARM64 and get
`ci-RUN_NUMBER.RUN_ATTEMPT`, source-SHA and unique build tags. The independent
`unvrs-backend`, `unvrs-frontend` and `unvrs-db` OCI charts share version
`0.1.0-ci.RUN_NUMBER.RUN_ATTEMPT`. Application charts lock exact image-index
digests; the database chart manages a database/role on existing `postgres-geo`.

## Credentials

Existing repository secrets `HARBOR_USERNAME` and `HARBOR_PASSWORD` belong to the
project-scoped CI robot. Argo CD and Kubernetes use separate pull-only robots.
The original UNVRS publishing robot has a one-year expiry; rotate it before
expiry. No new PAT or cluster credentials are needed for promotion.

Actions are pinned to commit SHAs. Only trusted main promotion code receives
contents/checks write permissions. The PR guard uses `pull_request_target` solely
to inspect filenames through GitHub's API, without executing feature code.

Keep published chart versions immutable and retain images referenced by release
history. GitOps-only and documentation commits do not start image builds.
