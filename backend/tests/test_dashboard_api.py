from datetime import datetime, timezone
import json
import os
import hashlib
import hmac
import pytest
from uuid import uuid4

from sqlalchemy import select
from app.models.entities import Incident, IncidentDiagnosis, RecoveryAttempt, Workflow


def send_failure(context, tenant_idx=0, operation_id="op-1", failed_step="step-1", status_code=503):
    client, _, ids, _, _, _ = context
    raw = json.dumps({
        "schema_version": "1.0",
        "event_id": f"evt-{uuid4().hex[:8]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "n8n",
        "source_execution_id": f"exec-{uuid4().hex[:8]}",
        "workflow_external_id": "notify-orders",
        "failed_step": failed_step,
        "operation_id": operation_id,
        "error": {"category": "PROVIDER_UNAVAILABLE", "message": f"Outage HTTP {status_code}", "http_status": status_code},
    }).encode()
    sig = "sha256=" + hmac.new(os.environ[f"TEST_WEBHOOK_{tenant_idx}"].encode(), raw, hashlib.sha256).hexdigest()
    res = client.post(
        "/api/v1/events/failure",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Integration-ID": ids[tenant_idx],
            "X-Webhook-Signature": sig,
        },
    )
    assert res.status_code == 202
    return res.json()["incident_id"]


def test_system_status_auth_and_content(context):
    client, _, _, tokens, _, _ = context
    # 401 on missing auth
    res = client.get("/api/v1/system/status")
    assert res.status_code == 401

    # 401 on invalid token
    res = client.get("/api/v1/system/status", headers={"Authorization": "Bearer invalid-token-" + "x" * 32})
    assert res.status_code == 401

    # 200 on valid token
    res = client.get("/api/v1/system/status", headers={"Authorization": f"Bearer {tokens[0]}"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["tenant_name"] == "Demo 0"
    assert data["recovery_mode"] == "mock-only"
    assert "ai_provider" in data
    assert "ai_model" in data


def test_dashboard_summary_zero_and_populated(context):
    client, sessions, _, tokens, _, _ = context
    # Zero incidents initially
    res = client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {tokens[0]}"})
    assert res.status_code == 200
    data = res.json()
    assert data["total_incidents"] == 0
    assert data["recovered_incidents"] == 0
    assert data["needs_attention"] == 0
    assert data["recovery_rate"] == 0.0
    assert data["rate_label"] == "Simulated Recovery Rate"
    assert data["mode"] == "mock-only"

    # Ingest an incident for tenant 0
    inc_id = send_failure(context, tenant_idx=0)

    # Check summary reflects new incident
    res = client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {tokens[0]}"})
    assert res.status_code == 200
    data = res.json()
    assert data["total_incidents"] == 1
    assert data["active_recovering"] == 1
    assert data["recovery_rate"] == 0.0

    # Cross-tenant isolation check: Tenant 1 should still see 0
    res_t1 = client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {tokens[1]}"})
    assert res_t1.status_code == 200
    assert res_t1.json()["total_incidents"] == 0


def test_dashboard_trends(context):
    client, _, _, tokens, _, _ = context
    res = client.get("/api/v1/dashboard/trends?days=7", headers={"Authorization": f"Bearer {tokens[0]}"})
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 7
    assert "date" in data[0]
    assert "incidents_created" in data[0]
    assert "incidents_recovered" in data[0]
    assert "incidents_escalated" in data[0]


def test_incidents_list_pagination_and_search(context):
    client, sessions, _, tokens, _, _ = context
    # Create 3 incidents with unique operations
    send_failure(context, tenant_idx=0, operation_id="search-target-alpha", failed_step="payment_step")
    send_failure(context, tenant_idx=0, operation_id="search-target-beta", failed_step="email_step")
    send_failure(context, tenant_idx=0, operation_id="other-gamma", failed_step="sms_step")

    # List all
    res = client.get("/api/v1/incidents", headers={"Authorization": f"Bearer {tokens[0]}"})
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    assert data["limit"] == 20
    assert data["offset"] == 0

    # Pagination: limit 1, offset 1
    res_page = client.get("/api/v1/incidents?limit=1&offset=1", headers={"Authorization": f"Bearer {tokens[0]}"})
    assert res_page.status_code == 200
    page_data = res_page.json()
    assert page_data["total"] == 3
    assert len(page_data["items"]) == 1

    # Search filter
    res_search = client.get("/api/v1/incidents?search=search-target", headers={"Authorization": f"Bearer {tokens[0]}"})
    assert res_search.status_code == 200
    search_data = res_search.json()
    assert search_data["total"] == 2

    # Status filter
    res_status = client.get("/api/v1/incidents?status=RECEIVED", headers={"Authorization": f"Bearer {tokens[0]}"})
    assert res_status.status_code == 200
    assert res_status.json()["total"] == 3

    res_empty_status = client.get("/api/v1/incidents?status=RECOVERED", headers={"Authorization": f"Bearer {tokens[0]}"})
    assert res_empty_status.status_code == 200
    assert res_empty_status.json()["total"] == 0

    # Tenant isolation
    res_t1 = client.get("/api/v1/incidents", headers={"Authorization": f"Bearer {tokens[1]}"})
    assert res_t1.status_code == 200
    assert res_t1.json()["total"] == 0


def test_workflows_and_integrations_list(context):
    client, _, _, tokens, _, _ = context
    # Workflows list
    res_wf = client.get("/api/v1/workflows", headers={"Authorization": f"Bearer {tokens[0]}"})
    assert res_wf.status_code == 200
    wfs = res_wf.json()
    assert len(wfs) >= 1
    assert wfs[0]["external_id"] == "notify-orders"
    assert wfs[0]["integration_kind"] == "n8n"

    # Integrations list
    res_int = client.get("/api/v1/integrations", headers={"Authorization": f"Bearer {tokens[0]}"})
    assert res_int.status_code == 200
    integrations = res_int.json()
    assert len(integrations) >= 1
    assert integrations[0]["kind"] == "n8n"
    # Ensure secrets are NEVER leaked in response
    assert "secret_ref" not in integrations[0]
    assert "secret" not in integrations[0]


def test_approvals_list(context):
    from uuid import UUID
    client, sessions, _, tokens, _, _ = context
    inc_id = UUID(send_failure(context, tenant_idx=0, operation_id="needs-approval-op"))

    # Manually transition incident to NEEDS_ATTENTION for testing
    with sessions() as db:
        inc = db.get(Incident, inc_id)
        inc.status = "NEEDS_ATTENTION"
        inc.recovery_reason = "AI_HUMAN_APPROVAL_REQUIRED"
        db.commit()

    res = client.get("/api/v1/approvals", headers={"Authorization": f"Bearer {tokens[0]}"})
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["incident_id"] == str(inc_id)
    assert items[0]["status"] == "NEEDS_ATTENTION"
    assert items[0]["escalation_reason"] == "AI_HUMAN_APPROVAL_REQUIRED"

    # Tenant 1 isolation
    res_t1 = client.get("/api/v1/approvals", headers={"Authorization": f"Bearer {tokens[1]}"})
    assert res_t1.status_code == 200
    assert len(res_t1.json()) == 0


def test_mock_primary_provider_failure_environment_guard(context):
    client, _, _, _, _, _ = context
    # In test/dev environment, returns 503
    res = client.post("/mock/primary-provider-failure")
    assert res.status_code == 503
    assert "Primary notification provider unavailable" in res.json()["detail"]
