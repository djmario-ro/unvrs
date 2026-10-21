#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' 'Staging is managed by Argo CD. Do not run helm upgrade on these releases.'
printf '%s\n' 'Run scripts/promote-staging.py CHART_VERSION, review, commit and push gitops/staging.'
