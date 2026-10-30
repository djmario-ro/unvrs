#!/usr/bin/env python3
"""One-time, destructive v1 → staff-app reset of the dedicated staging schema.

Pause backend Argo reconciliation and scale the old backend to zero first.
This never deletes the CNPG cluster, database, role, or Kubernetes credentials.
"""
import argparse
import json
import re
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True, help='Explicit kubectl context')
    parser.add_argument('--image', required=True, help='Published backend repository@sha256:digest')
    parser.add_argument('--confirm-reset', required=True, choices=['unvrs_staging'])
    args = parser.parse_args()
    if not re.fullmatch(r'harbor\.cloud\.retreat480\.com/unvrs/backend@sha256:[a-f0-9]{64}', args.image):
        parser.error('Use the digest-locked UNVRS backend image from the new release')
    kubectl = ['kubectl', '--context', args.context, '-n', 'unvrs-staging']

    def get(*resource):
        return json.loads(subprocess.check_output([*kubectl, 'get', *resource, '-o', 'json']))

    application = json.loads(subprocess.check_output([
        'kubectl', '--context', args.context, '-n', 'argocd', 'get',
        'application', 'unvrs-backend', '-o', 'json',
    ]))
    root = json.loads(subprocess.check_output([
        'kubectl', '--context', args.context, '-n', 'argocd', 'get',
        'application', 'unvrs-staging-root', '-o', 'json',
    ]))
    for app in (root, application):
        if app['spec'].get('syncPolicy', {}).get('automated') is not None:
            parser.error(f"Pause automatic sync for {app['metadata']['name']} before resetting")
        if app.get('operation') or app.get('status', {}).get('operationState', {}).get('phase') in ('Running', 'Terminating'):
            parser.error(f"Wait for {app['metadata']['name']} sync to finish before resetting")
    deployment = get('deployment', 'unvrs-backend')
    if deployment['spec'].get('replicas', 1) != 0 or deployment.get('status', {}).get('replicas', 0) != 0:
        parser.error('Scale unvrs-backend to zero and wait for all old pods to terminate')

    # Validate the connection identity inside the Job before issuing destructive SQL.
    reset = '''import asyncio, os
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

async def main():
    url = make_url(os.environ["DATABASE_URL"])
    assert url.database == "unvrs_staging", "Unexpected database"
    assert url.username == "unvrs_staging", "Unexpected role"
    assert url.host == "postgres-geo-rw.postgres.svc.cluster.local", "Unexpected host"
    assert url.query.get("ssl") == "require", "TLS is required"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        assert (await conn.execute(text("SELECT current_database()"))).scalar_one() == "unvrs_staging"
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public AUTHORIZATION unvrs_staging"))
    await engine.dispose()

asyncio.run(main())
'''
    job = {
        'apiVersion': 'batch/v1', 'kind': 'Job',
        'metadata': {'generateName': 'unvrs-schema-reset-', 'namespace': 'unvrs-staging'},
        'spec': {
            'backoffLimit': 0, 'activeDeadlineSeconds': 180,
            'template': {'spec': {
                'restartPolicy': 'Never',
                'imagePullSecrets': [{'name': 'harbor-unvrs-pull'}],
                'containers': [{
                    'name': 'reset', 'image': args.image,
                    'command': ['python', '-c', reset],
                    'envFrom': [{'secretRef': {'name': 'unvrs-backend-credentials'}}],
                    'resources': {'requests': {'cpu': '100m', 'memory': '128Mi'},
                                  'limits': {'cpu': '1', 'memory': '512Mi'}},
                }],
            }},
        },
    }
    result = subprocess.check_output([*kubectl, 'create', '-f', '-', '-o', 'json'], input=json.dumps(job).encode())
    name = json.loads(result)['metadata']['name']
    print('Reset Job:', name, flush=True)
    subprocess.run([*kubectl, 'wait', '--for=condition=complete', f'job/{name}', '--timeout=190s'], check=True)
    print('Schema reset complete. Promote the new backend chart to apply Alembic migrations.')


if __name__ == '__main__':
    main()
