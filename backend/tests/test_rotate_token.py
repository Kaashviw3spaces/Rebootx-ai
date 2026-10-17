import os
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select

from app.models.entities import Integration, Tenant, Workflow
from scripts.rotate_token import rotate_tenant_token


def test_successful_rotation_and_auth(context):
    client, sessions, ids, tokens, engine, _ = context
    # Retrieve tenant 0
    with sessions() as db:
        tenant_0 = db.scalar(select(Tenant).order_by(Tenant.name))
        tenant_id = tenant_0.id
        old_hash = tenant_0.read_token_hash

    # 1. Previous token authenticates successfully
    res_before = client.get("/api/v1/system/status", headers={"Authorization": f"Bearer {tokens[0]}"})
    assert res_before.status_code == 200
    assert res_before.json()["tenant_id"] == str(tenant_id)

    # 2. Rotate the token
    db_url = os.environ["DATABASE_URL"]
    tenant_name, new_token = rotate_tenant_token(db_url, tenant_id)

    assert tenant_name == "Demo 0"
    assert new_token != tokens[0]
    assert len(new_token) >= 32

    # 3. Previous token is now rejected with 401
    res_old = client.get("/api/v1/system/status", headers={"Authorization": f"Bearer {tokens[0]}"})
    assert res_old.status_code == 401

    # 4. New token authenticates successfully with 200
    res_new = client.get("/api/v1/system/status", headers={"Authorization": f"Bearer {new_token}"})
    assert res_new.status_code == 200
    assert res_new.json()["tenant_id"] == str(tenant_id)
    assert res_new.json()["tenant_name"] == "Demo 0"

    # 5. Database verify: read_token_hash changed
    with sessions() as db:
        refreshed = db.get(Tenant, tenant_id)
        assert refreshed.read_token_hash != old_hash


def test_preservation_of_integration_and_workflow_records(context):
    client, sessions, ids, tokens, _, _ = context
    db_url = os.environ["DATABASE_URL"]

    # Capture initial state
    with sessions() as db:
        tenant = db.scalar(select(Tenant).order_by(Tenant.name))
        tenant_id = tenant.id
        tenant_name = tenant.name
        created_at = tenant.created_at

        integration = db.scalar(select(Integration).where(Integration.tenant_id == tenant_id))
        integ_id = integration.id
        integ_kind = integration.kind
        integ_secret_ref = integration.secret_ref

        workflow = db.scalar(select(Workflow).where(Workflow.tenant_id == tenant_id))
        wf_id = workflow.id
        wf_ext_id = workflow.external_id
        wf_kind = workflow.kind

    # Rotate token
    _, new_token = rotate_tenant_token(db_url, tenant_id)

    # Verify everything else is strictly preserved
    with sessions() as db:
        refreshed_tenant = db.get(Tenant, tenant_id)
        assert refreshed_tenant.id == tenant_id
        assert refreshed_tenant.name == tenant_name
        assert refreshed_tenant.created_at == created_at

        refreshed_integ = db.get(Integration, integ_id)
        assert refreshed_integ.id == integ_id
        assert refreshed_integ.tenant_id == tenant_id
        assert refreshed_integ.kind == integ_kind
        assert refreshed_integ.secret_ref == integ_secret_ref

        refreshed_wf = db.get(Workflow, wf_id)
        assert refreshed_wf.id == wf_id
        assert refreshed_wf.tenant_id == tenant_id
        assert refreshed_wf.external_id == wf_ext_id
        assert refreshed_wf.kind == wf_kind


def test_missing_tenant_fails_safely(context):
    _, sessions, _, _, _, _ = context
    db_url = os.environ["DATABASE_URL"]
    missing_id = uuid4()

    # Capture initial count of tenants
    with sessions() as db:
        count_before = len(db.scalars(select(Tenant)).all())

    # Attempt rotation on non-existent tenant
    with pytest.raises(LookupError, match=f"Tenant not found: {missing_id}"):
        rotate_tenant_token(db_url, missing_id)

    # Confirm no records were created or modified
    with sessions() as db:
        count_after = len(db.scalars(select(Tenant)).all())
        assert count_after == count_before


def test_invalid_token_length_rejection(context):
    _, sessions, _, tokens, _, _ = context
    db_url = os.environ["DATABASE_URL"]

    with sessions() as db:
        tenant = db.scalar(select(Tenant).order_by(Tenant.name))
        tenant_id = tenant.id
        original_hash = tenant.read_token_hash

    # Less than 32 chars
    with pytest.raises(ValueError, match="between 32 and 512 characters"):
        rotate_tenant_token(db_url, tenant_id, custom_token="too-short")

    # Verify hash was not modified
    with sessions() as db:
        refreshed = db.get(Tenant, tenant_id)
        assert refreshed.read_token_hash == original_hash

