import hashlib
import hmac
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import func, select
from temporalio.testing import ActivityEnvironment

from app.core.config import Settings
from app.models.entities import AuditLog, Incident, RecoveryAttempt, RecoveryOutbox
from app.schemas.events import FailureEvent
from app.temporal.activities import RecoveryActivities
from app.temporal.dispatcher import OutboxDispatcher
from app.temporal.schemas import StepRequest, recovery_workflow_id


REPO_ROOT = Path(__file__).resolve().parents[2]
N8N_DIR = REPO_ROOT / 'integrations' / 'n8n'
FORMATTER_JS = N8N_DIR / 'code_nodes' / 'format_and_sign_failure.js'


def run_js_formatter(context_dict, config_dict):
    eval_code = f"""
    const {{ formatAndSignFailure, hmacSha256 }} = require({json.dumps(str(FORMATTER_JS))});
    const result = formatAndSignFailure({json.dumps(context_dict)}, {json.dumps(config_dict)});
    process.stdout.write(JSON.stringify(result));
    """
    proc = subprocess.run(['node', '-e', eval_code], capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def test_n8n_workflow_json_validity():
    """Verify both exportable n8n workflows are valid JSON and contain expected nodes."""
    error_wf_path = N8N_DIR / 'workflows' / 'rebootx_error_handler.json'
    primary_wf_path = N8N_DIR / 'workflows' / 'primary_order_notification.json'

    assert error_wf_path.exists()
    assert primary_wf_path.exists()

    error_wf = json.loads(error_wf_path.read_text(encoding='utf-8'))
    primary_wf = json.loads(primary_wf_path.read_text(encoding='utf-8'))

    # Verify error workflow nodes and connections
    assert error_wf['name'] == 'REBOOTX Error Handler'
    error_node_types = {n['type'] for n in error_wf['nodes']}
    assert 'n8n-nodes-base.errorTrigger' in error_node_types
    assert 'n8n-nodes-base.code' in error_node_types
    assert 'n8n-nodes-base.httpRequest' in error_node_types

    code_node = next(n for n in error_wf['nodes'] if n['type'] == 'n8n-nodes-base.code')
    assert 'hmacSha256' in code_node['parameters']['jsCode']
    assert 'formatAndSignFailure' in code_node['parameters']['jsCode']

    # Verify primary workflow has errorWorkflow setting
    assert primary_wf['name'] == 'Primary Order Notification Dispatcher'
    assert primary_wf['settings']['errorWorkflow'] in {'REBOOTX Error Handler', 'wmtArUNSGBtEuCUM'}


def test_js_hmac_parity_with_python():
    """Verify that pure JS and Node crypto HMAC-SHA256 match Python hashlib byte-for-byte."""
    secret = 'super-secret-key-that-is-at-least-32-chars-long-123456'
    payloads = [
        '{"test":"simple"}',
        '{"schema_version":"1.0","special":"@#$%^&*()_+-=[]{}|;:,.<>/?"}',
        '{"unicode":"こんにちは世界"}',
        '',
        json.dumps({'large_array': list(range(100))}),
    ]

    for p in payloads:
        expected_py = hmac.new(secret.encode('utf-8'), p.encode('utf-8'), hashlib.sha256).hexdigest()

        eval_code = f"""
        const {{ hmacSha256 }} = require({json.dumps(str(FORMATTER_JS))});
        const crypto = require('crypto');
        const custom = hmacSha256({json.dumps(secret)}, {json.dumps(p)});
        const native = crypto.createHmac('sha256', {json.dumps(secret)}).update({json.dumps(p)}).digest('hex');
        process.stdout.write(JSON.stringify({{ custom, native }}));
        """
        proc = subprocess.run(['node', '-e', eval_code], capture_output=True, text=True, check=True)
        out = json.loads(proc.stdout)

        assert out['custom'] == expected_py
        assert out['native'] == expected_py


def test_n8n_payload_mapping_conforms_to_schema():
    """Verify output of formatAndSignFailure conforms strictly to FailureEvent Pydantic schema."""
    input_ctx = {
        'execution': {
            'id': '9876',
            'lastNodeExecuted': 'Send Confirmation Email',
            'error': {'message': 'HTTP 503 Backend Service Unavailable', 'statusCode': 503}
        },
        'workflow': {'name': 'notify-orders'}
    }
    config = {
        'baseUrl': 'http://127.0.0.1:8000',
        'integrationId': '00000000-0000-0000-0000-000000000000',
        'webhookSecret': 'a' * 32,
        'workflowExternalId': 'notify-orders'
    }

    res = run_js_formatter(input_ctx, config)
    parsed = FailureEvent.model_validate_json(res['payload'])
    assert parsed.source == 'n8n'
    assert parsed.source_execution_id == '9876'
    assert parsed.failed_step == 'Send_Confirmation_Email'
    assert parsed.error.category == 'PROVIDER_UNAVAILABLE'
    assert parsed.error.http_status == 503


def test_n8n_stable_event_id():
    """Ensure event_id is deterministic across repeated calls for the same execution failure."""
    input_ctx = {
        'execution': {
            'id': 'exec-stable-101',
            'lastNodeExecuted': 'Payment Step',
            'error': {'message': 'Network timeout'}
        },
        'workflow': {'name': 'notify-orders'}
    }
    config = {
        'baseUrl': 'http://127.0.0.1:8000',
        'integrationId': '00000000-0000-0000-0000-000000000000',
        'webhookSecret': 'a' * 32,
        'workflowExternalId': 'notify-orders'
    }

    res1 = run_js_formatter(input_ctx, config)
    res2 = run_js_formatter(input_ctx, config)

    assert res1['event']['event_id'] == res2['event']['event_id']
    assert res1['event']['event_id'] == 'n8n:exec-stable-101:Payment_Step'


def test_n8n_event_ingestion_valid_hmac(context):
    """End-to-end webhook ingestion of a real n8n JS-formatted failure payload."""
    client, sessions, ids, _, _, _ = context
    integration_id = ids[0]
    secret = os.environ['TEST_WEBHOOK_0']

    input_ctx = {
        'execution': {
            'id': 'exec-2001',
            'lastNodeExecuted': 'Send Confirmation',
            'error': {'message': 'HTTP 503 Downstream Unavailable', 'statusCode': 503}
        },
        'workflow': {'name': 'notify-orders'}
    }
    config = {
        'baseUrl': 'http://127.0.0.1:8000',
        'integrationId': integration_id,
        'webhookSecret': secret,
        'workflowExternalId': 'notify-orders'
    }

    res = run_js_formatter(input_ctx, config)
    resp = client.post('/api/v1/events/failure', content=res['payload'].encode('utf-8'), headers=res['headers'])

    assert resp.status_code == 202
    data = resp.json()
    assert data['status'] == 'RECEIVED'
    assert data['duplicate'] is False

    with sessions() as db:
        incident = db.get(Incident, UUID(data['incident_id']))
        assert incident is not None
        assert incident.source == 'n8n'
        assert incident.source_execution_id == 'exec-2001'
        assert incident.failed_step == 'Send_Confirmation'
        assert incident.failure_type == 'PROVIDER_UNAVAILABLE'
        assert incident.error_details['message'] == '[REDACTED]'
        assert incident.error_details['http_status'] == 503

        # Transactional outbox was created
        outbox = db.scalar(select(RecoveryOutbox).where(RecoveryOutbox.incident_id == incident.id))
        assert outbox is not None
        assert outbox.temporal_workflow_id == recovery_workflow_id(incident.tenant_id, incident.id)


def test_n8n_invalid_hmac_rejected(context):
    """Tampering with n8n payload or signature fails closed with 401."""
    client, _, ids, _, _, _ = context
    secret = os.environ['TEST_WEBHOOK_0']

    input_ctx = {'execution': {'id': 'exec-3001'}, 'workflow': {'name': 'notify-orders'}}
    config = {'integrationId': ids[0], 'webhookSecret': secret, 'workflowExternalId': 'notify-orders'}
    res = run_js_formatter(input_ctx, config)

    # Tamper payload
    tampered_body = res['payload'].encode('utf-8') + b' '
    resp = client.post('/api/v1/events/failure', content=tampered_body, headers=res['headers'])
    assert resp.status_code == 401

    # Tamper signature
    bad_headers = dict(res['headers'])
    bad_headers['X-Webhook-Signature'] = 'sha256=' + '0' * 64
    resp2 = client.post('/api/v1/events/failure', content=res['payload'].encode('utf-8'), headers=bad_headers)
    assert resp2.status_code == 401


def test_n8n_timestamp_validation(context):
    """Stale n8n event timestamps outside +/- 300s window are rejected."""
    client, _, ids, _, _, _ = context
    secret = os.environ['TEST_WEBHOOK_0']

    old_time = (datetime.now(timezone.utc) - timedelta(seconds=305)).isoformat()
    input_ctx = {'execution': {'id': 'exec-4001'}, 'workflow': {'name': 'notify-orders'}}
    config = {
        'integrationId': ids[0],
        'webhookSecret': secret,
        'workflowExternalId': 'notify-orders',
        'timestampOverride': old_time
    }
    res = run_js_formatter(input_ctx, config)

    resp = client.post('/api/v1/events/failure', content=res['payload'].encode('utf-8'), headers=res['headers'])
    assert resp.status_code == 401
    assert resp.json()['detail'] == 'Event timestamp outside allowed tolerance'


def test_n8n_duplicate_event_delivery(context):
    """Multiple deliveries of the same n8n failure return duplicate: true with single DB row."""
    client, sessions, ids, _, _, _ = context
    secret = os.environ['TEST_WEBHOOK_0']

    input_ctx = {
        'execution': {'id': 'exec-dedup-5001', 'lastNodeExecuted': 'HTTP_Send'},
        'workflow': {'name': 'notify-orders'}
    }
    config = {'integrationId': ids[0], 'webhookSecret': secret, 'workflowExternalId': 'notify-orders'}
    res = run_js_formatter(input_ctx, config)

    resp1 = client.post('/api/v1/events/failure', content=res['payload'].encode('utf-8'), headers=res['headers'])
    assert resp1.status_code == 202
    assert resp1.json()['duplicate'] is False
    inc_id = resp1.json()['incident_id']

    # Send again
    resp2 = client.post('/api/v1/events/failure', content=res['payload'].encode('utf-8'), headers=res['headers'])
    assert resp2.status_code == 202
    assert resp2.json()['duplicate'] is True
    assert resp2.json()['incident_id'] == inc_id

    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(Incident)) == 1
        assert db.scalar(select(func.count()).select_from(RecoveryOutbox)) == 1
        assert db.scalar(select(func.count()).select_from(AuditLog)) == 1


def test_n8n_missing_execution_identifiers_safe_handling(context):
    """Safely handles missing or empty n8n execution/error metadata without crashing or 422."""
    client, _, ids, _, _, _ = context
    secret = os.environ['TEST_WEBHOOK_0']

    # Bare empty context
    input_ctx = {}
    config = {'integrationId': ids[0], 'webhookSecret': secret, 'workflowExternalId': 'notify-orders'}
    res = run_js_formatter(input_ctx, config)

    resp = client.post('/api/v1/events/failure', content=res['payload'].encode('utf-8'), headers=res['headers'])
    assert resp.status_code == 202
    assert resp.json()['status'] == 'RECEIVED'


def test_n8n_tenant_isolation(context):
    """Cross-tenant credentials and access are rejected."""
    client, _, ids, tokens, _, _ = context
    secret_0 = os.environ['TEST_WEBHOOK_0']
    secret_1 = os.environ['TEST_WEBHOOK_1']

    # Tenant 0 sends event
    input_ctx = {'execution': {'id': 'exec-tenant-0'}, 'workflow': {'name': 'notify-orders'}}
    res0 = run_js_formatter(input_ctx, {'integrationId': ids[0], 'webhookSecret': secret_0})
    resp0 = client.post('/api/v1/events/failure', content=res0['payload'].encode('utf-8'), headers=res0['headers'])
    assert resp0.status_code == 202
    inc_id_0 = resp0.json()['incident_id']

    # Tenant 1 cannot read Tenant 0's incident
    read_resp = client.get(f'/api/v1/incidents/{inc_id_0}', headers={'Authorization': f'Bearer {tokens[1]}'})
    assert read_resp.status_code == 404

    # Sign with Tenant 1 secret but provide Tenant 0 Integration ID -> 401
    bad_res = run_js_formatter(input_ctx, {'integrationId': ids[0], 'webhookSecret': secret_1})
    bad_resp = client.post('/api/v1/events/failure', content=bad_res['payload'].encode('utf-8'), headers=bad_res['headers'])
    assert bad_resp.status_code == 401


def test_n8n_temporal_dispatch_and_mock_recovery(context):
    """Ingest n8n failure event, claim via outbox, and run recovery through Temporal activities to RECOVERED."""
    client, sessions, ids, tokens, _, _ = context
    secret = os.environ['TEST_WEBHOOK_0']

    input_ctx = {
        'execution': {'id': 'exec-recover-7001', 'lastNodeExecuted': 'Send_Confirmation'},
        'workflow': {'name': 'notify-orders'},
        'error': {'message': 'HTTP 503 Provider Unavailable', 'statusCode': 503}
    }
    res = run_js_formatter(input_ctx, {'integrationId': ids[0], 'webhookSecret': secret})
    resp = client.post('/api/v1/events/failure', content=res['payload'].encode('utf-8'), headers=res['headers'])
    assert resp.status_code == 202
    inc_id = UUID(resp.json()['incident_id'])

    # Verify OutboxDispatcher claims the row
    settings = Settings(database_url=str(context[4].url), ai_provider='mock')
    dispatcher = OutboxDispatcher(sessions, settings)
    claim = dispatcher.claim()
    assert claim is not None
    assert claim.data.incident_id == str(inc_id)

    # Execute recovery activities
    activities = RecoveryActivities(sessions, settings)
    env = ActivityEnvironment()
    req = StepRequest(claim.data, 'accept')
    for op in ['accept', 'diagnose', 'plan', 'retry', 'fallback', 'verify', 'recover']:
        res_step = env.run(activities.step, StepRequest(claim.data, op))

    # Acknowledge dispatch
    dispatcher.finish(claim)

    with sessions() as db:
        inc = db.get(Incident, inc_id)
        assert inc.status == 'RECOVERED'
        assert inc.verification_outcome == 'MOCK_VERIFIED'
        attempts = db.scalars(select(RecoveryAttempt).where(RecoveryAttempt.incident_id == inc_id)).all()
        assert len(attempts) >= 2  # retry + fallback attempts

    # Tenant can read recovery status
    read_recovery = client.get(f'/api/v1/incidents/{inc_id}/recovery', headers={'Authorization': f'Bearer {tokens[0]}'})
    assert read_recovery.status_code == 200
    rec_data = read_recovery.json()
    assert rec_data['status'] == 'RECOVERED'
    assert rec_data['verification_outcome'] == 'MOCK_VERIFIED'


def test_n8n_escalation_behavior(context):
    """Unrecoverable failure (e.g. 401 AUTHENTICATION_FAILURE) escalates to NEEDS_ATTENTION."""
    client, sessions, ids, _, _, _ = context
    secret = os.environ['TEST_WEBHOOK_0']

    input_ctx = {
        'execution': {'id': 'exec-escalate-8001', 'lastNodeExecuted': 'Auth_Node'},
        'workflow': {'name': 'notify-orders'},
        'error': {'message': 'HTTP 401 Unauthorized', 'statusCode': 401}
    }
    res = run_js_formatter(input_ctx, {'integrationId': ids[0], 'webhookSecret': secret})
    resp = client.post('/api/v1/events/failure', content=res['payload'].encode('utf-8'), headers=res['headers'])
    inc_id = UUID(resp.json()['incident_id'])

    settings = Settings(database_url=str(context[4].url), ai_provider='mock')
    dispatcher = OutboxDispatcher(sessions, settings)
    claim = dispatcher.claim()

    activities = RecoveryActivities(sessions, settings)
    env = ActivityEnvironment()
    env.run(activities.step, StepRequest(claim.data, 'accept'))
    diag_res = env.run(activities.step, StepRequest(claim.data, 'diagnose'))
    # Escalation step
    env.run(activities.step, StepRequest(claim.data, 'escalate', reason=diag_res.category))

    with sessions() as db:
        inc = db.get(Incident, inc_id)
        assert inc.status == 'NEEDS_ATTENTION'
        assert inc.recovery_reason == 'AUTHENTICATION_FAILURE'


def test_mock_primary_provider_endpoint(context):
    """Verify demo failure injection endpoint returns HTTP 503."""
    client, _, _, _, _, _ = context
    resp = client.post('/mock/primary-provider-failure')
    assert resp.status_code == 503
    assert 'unavailable' in resp.json()['detail']

