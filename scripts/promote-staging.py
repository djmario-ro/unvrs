#!/usr/bin/env python3
"""Record an explicit published chart version for all staging applications."""
import argparse
from pathlib import Path
import re

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('version', help='Published chart version, e.g. 0.1.0-ci.2.1')
a = p.parse_args()
if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?', a.version):
    p.error('An explicit SemVer chart version is required')
root = Path(__file__).resolve().parents[1] / 'gitops/staging'
root.mkdir(parents=True, exist_ok=True)
for component, wave in [('db', 0), ('backend', 10), ('frontend', 20)]:
    namespace = 'postgres' if component == 'db' else 'unvrs-staging'
    text = f'''apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: unvrs-{component}
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "{wave}"
spec:
  project: unvrs-staging
  source:
    repoURL: harbor.cloud.retreat480.com/unvrs
    chart: unvrs-{component}
    targetRevision: {a.version}
    helm:
      releaseName: unvrs-{component}
  destination:
    server: https://kubernetes.default.svc
    namespace: {namespace}
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
'''
    (root / f'{component}.yaml').write_text(text)
print('Staging chart versions set to', a.version)
print('Commit and push gitops/staging to promote; reverting that commit rolls back.')
