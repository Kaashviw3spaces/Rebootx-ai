"""Submit one synthetic signed failure event. No notification/recovery is executed."""
import argparse
import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from dotenv import load_dotenv

from app.core.security import resolve_secret


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--integration-id', required=True)
    parser.add_argument('--secret-env', default='N8N_WEBHOOK_SECRET')
    parser.add_argument('--workflow-external-id', default='notify-orders')
    parser.add_argument('--event-id', default=None)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    load_dotenv()
    event_id = args.event_id or 'demo-' + uuid4().hex
    event = {
        'schema_version': '1.0', 'event_id': event_id,
        'timestamp': datetime.now(timezone.utc).isoformat(), 'source': 'n8n',
        'source_execution_id': 'exec-' + event_id,
        'workflow_external_id': args.workflow_external_id,
        'failed_step': 'send_confirmation', 'operation_id': 'op-' + event_id,
        'error': {'category': 'PROVIDER_UNAVAILABLE', 'message': 'Synthetic HTTP 503'},
    }
    raw = json.dumps(event, separators=(',', ':')).encode()
    signature = hmac.new(resolve_secret(args.secret_env).encode(), raw, hashlib.sha256).hexdigest()
    response = httpx.post(args.base_url.rstrip('/') + '/api/v1/events/failure', content=raw, headers={
        'Content-Type': 'application/json', 'X-Integration-ID': args.integration_id,
        'X-Webhook-Signature': 'sha256=' + signature,
    }, timeout=10)
    response.raise_for_status()
    print(response.text)


if __name__ == '__main__':
    main()
