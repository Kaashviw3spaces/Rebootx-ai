"""Read a failed execution's saved workflow and print its authorization fingerprint.

Review the workflow in n8n before authorizing; this command grants no permission.
"""
import argparse
from app.core.config import Settings
from app.integrations.n8n.client import N8nClient, N8nError, workflow_fingerprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execution-id', required=True)
    parser.add_argument('--workflow-id', required=True)
    args = parser.parse_args()
    client = None
    try:
        client = N8nClient(Settings())
        execution_id = client.execution_id(args.execution_id)
        data = client.request('GET', f'executions/{execution_id}', params={'includeData': 'true'})
        client.parse(data, args.workflow_id, execution_id)
        if not isinstance(data.get('workflowData'), dict):
            raise N8nError('N8N_MISSING_WORKFLOW_SNAPSHOT')
        print(workflow_fingerprint(data['workflowData']))
    except N8nError as exc:
        raise SystemExit(str(exc)) from None
    finally:
        if client:
            client.close()


if __name__ == '__main__':
    main()
