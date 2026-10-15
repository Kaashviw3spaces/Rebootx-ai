"""Simulate an n8n Error Trigger execution by invoking format_and_sign_failure.js via Node.js."""
import argparse
import json
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import load_dotenv

from app.core.security import resolve_secret


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--integration-id', required=True, help='UUID of the registered n8n integration')
    parser.add_argument('--secret-env', default='N8N_WEBHOOK_SECRET', help='Env var storing the webhook secret')
    parser.add_argument('--workflow-external-id', default='notify-orders', help='External workflow reference')
    parser.add_argument('--execution-id', default=None, help='Simulated n8n execution ID (default: deterministic random)')
    parser.add_argument('--failed-step', default='Send_Customer_Confirmation', help='Failed node name')
    parser.add_argument('--error-message', default='HTTP 503 Service Unavailable', help='Simulated error message')
    parser.add_argument('--base-url', default='http://127.0.0.1:8000', help='REBOOTX API base URL')
    args = parser.parse_args()

    load_dotenv()
    secret = resolve_secret(args.secret_env)
    exec_id = args.execution_id or f"exec-{uuid4().hex[:8]}"

    repo_root = Path(__file__).resolve().parents[2]
    js_script = repo_root / "integrations" / "n8n" / "code_nodes" / "format_and_sign_failure.js"

    input_context = {
        "execution": {
            "id": exec_id,
            "lastNodeExecuted": args.failed_step,
            "error": {"message": args.error_message}
        },
        "workflow": {"name": args.workflow_external_id}
    }

    config = {
        "baseUrl": args.base_url,
        "integrationId": args.integration_id,
        "webhookSecret": secret,
        "workflowExternalId": args.workflow_external_id
    }

    # Execute the actual JavaScript formatter via Node.js to guarantee real JS parity
    eval_code = f"""
    const {{ formatAndSignFailure }} = require({json.dumps(str(js_script))});
    const result = formatAndSignFailure({json.dumps(input_context)}, {json.dumps(config)});
    process.stdout.write(JSON.stringify(result));
    """
    proc = subprocess.run(["node", "-e", eval_code], capture_output=True, text=True, check=True)
    js_output = json.loads(proc.stdout)

    endpoint = js_output["endpoint"]
    headers = js_output["headers"]
    payload_bytes = js_output["payload"].encode("utf-8")

    print(f"Posting n8n failure event to {endpoint}...")
    print(f"Headers: {headers}")
    print(f"Payload: {js_output['payload']}")

    response = httpx.post(endpoint, content=payload_bytes, headers=headers, timeout=10.0)
    print(f"Response ({response.status_code}): {response.text}")
    response.raise_for_status()


if __name__ == '__main__':
    main()

