"""Register one tenant, integration, and workflow; never create tables implicitly."""
import argparse
import getpass
import re

from dotenv import load_dotenv

from app.core.config import Settings
from app.core.database import make_engine, session_factory
from app.core.security import resolve_secret, token_hash
from app.models.entities import Integration, Tenant, Workflow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant-name', required=True)
    parser.add_argument('--workflow-external-id', required=True)
    parser.add_argument('--secret-env', required=True, help='Dedicated environment variable for this integration secret')
    parser.add_argument('--workflow-kind', choices=['notification_v1', 'side_effect_safe_demo_v1'], default='notification_v1')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,199}', args.secret_env):
        parser.error('Use an uppercase environment variable name')
    if not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,200}', args.workflow_external_id):
        parser.error('Invalid workflow reference')
    if not 1 <= len(args.tenant_name) <= 200:
        parser.error('Tenant name must contain 1-200 characters')
    load_dotenv()
    resolve_secret(args.secret_env)
    token = getpass.getpass('Tenant read token (random, at least 32 characters): ')
    if not 32 <= len(token) <= 512:
        parser.error('Read token must contain 32-512 characters')
    engine = make_engine(Settings().database_url.get_secret_value())
    try:
        with session_factory(engine)() as db:
            tenant = Tenant(name=args.tenant_name, read_token_hash=token_hash(token))
            db.add(tenant)
            db.flush()
            integration = Integration(tenant_id=tenant.id, secret_ref=args.secret_env, kind='n8n')
            db.add(integration)
            db.flush()
            workflow = Workflow(tenant_id=tenant.id, integration_id=integration.id, external_id=args.workflow_external_id, kind=args.workflow_kind)
            db.add(workflow)
            db.commit()
            print(f'Tenant ID: {tenant.id}')
            print(f'Integration ID: {integration.id}')
            print(f'Workflow ID: {workflow.id}')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
