"""Verification helper for Checkpoint 6 isolated recovery demonstration."""
import argparse
import sys
from pathlib import Path
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.core.database import make_engine, session_factory
from app.models.entities import Incident, RecoveryAttempt, AuditLog


def check_isolation():
    settings = Settings()
    url_str = settings.database_url.get_secret_value()
    u = make_url(url_str)
    assert u.get_backend_name() == 'sqlite', f"Forbidden driver: {u.get_backend_name()}"
    db_path = str(Path(u.database).resolve())
    assert 'cp6-prep-7163e9b9ff1143aeaa6e72939962467f' in db_path, f"Unexpected DB path: {db_path}"
    
    # Assert N8N_AUTHORIZATIONS is a list containing exactly one valid N8nAuthorization object
    assert isinstance(settings.n8n_authorizations, list), f"Expected list, got {type(settings.n8n_authorizations)}"
    assert len(settings.n8n_authorizations) == 1, f"Expected 1 authorization, got {len(settings.n8n_authorizations)}"
    auth = settings.n8n_authorizations[0]
    assert str(auth.tenant_id) == '0610d06e-460f-465e-8b19-f80b336fd8e7'
    assert str(auth.integration_id) == '38979968-2d1f-4fd0-9307-c829e54ba58f'
    assert auth.workflow_external_id == 'ievg2u7YcfdnU3L8'
    assert auth.operation == 'retry_execution'
    assert auth.idempotent is True
    assert auth.side_effect_safe is True
    assert auth.workflow_sha256 == '34562e136ce84efed16d4faa31d28e62d10613cb8c363c51e3a372791c12526b'
    print("DATABASE_ISOLATION_ASSERTION_PASSED")


def check_provenance():
    url_str = Settings().database_url.get_secret_value()
    engine = make_engine(url_str)
    try:
        with session_factory(engine)() as db:
            inc = db.query(Incident).order_by(Incident.created_at.desc()).first()
            assert inc is not None, "No incident found in demo.db!"
            print(f"\n================ REBOOTX DB PROVENANCE ================")
            print(f"Incident ID:             {inc.id}")
            print(f"Terminal Status:         {inc.status}")
            print(f"Recovery Mode:           {inc.recovery_mode}")
            print(f"Verification Outcome:    {inc.verification_outcome}")
            assert inc.status == 'RECOVERED', f"Expected status RECOVERED, got {inc.status}"
            assert inc.verification_outcome == 'REAL_RECOVERY_VERIFIED', f"Expected REAL_RECOVERY_VERIFIED, got {inc.verification_outcome}"
            
            attempt = db.query(RecoveryAttempt).filter(RecoveryAttempt.incident_id == inc.id).first()
            if attempt:
                print(f"External Action Key:     {attempt.external_action_key}")
                print(f"Attempt Outcome:         {attempt.outcome}")
                print(f"Evidence:                {attempt.evidence}")
            print("========================================================")
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-isolation', action='store_true')
    parser.add_argument('--check-provenance', action='store_true')
    args = parser.parse_args()

    if args.check_isolation:
        check_isolation()
    elif args.check_provenance:
        check_provenance()
    else:
        parser.error("Specify --check-isolation or --check-provenance")


if __name__ == '__main__':
    main()

