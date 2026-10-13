"""Allowlisted structured logs; no raw exception messages or payloads."""
import json
import logging

logger = logging.getLogger('rebootx.recovery')


def log_event(event: str, **fields):
    allowed = {'incident_id', 'tenant_id', 'operation', 'state', 'attempt_count', 'error_code'}
    logger.info(json.dumps({'event': event, **{k: str(v) for k, v in fields.items() if k in allowed}}, sort_keys=True))
