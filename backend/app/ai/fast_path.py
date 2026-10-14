"""Conservative classification of structured evidence, never free-form messages."""
from app.ai.schemas import Diagnosis, DiagnosisInput

CONNECTION_TIMEOUT_CODES = frozenset({'CONNECTION_TIMEOUT', 'CONNECT_TIMEOUT'})
SCHEMA_ERROR_CODES = frozenset({'SCHEMA_VALIDATION_ERROR', 'INVALID_PAYLOAD'})


def classify_structured_failure(data: DiagnosisInput) -> Diagnosis | None:
    # Denials take precedence over retryable HTTP evidence; policy independently checks both.
    if data.http_status == 401 or data.failure_code == 'AUTHENTICATION_FAILURE':
        category, cause, explanation, approval = (
            'AUTHENTICATION_ERROR', 'Authentication was rejected.',
            'Structured authentication evidence requires review; the precise credential cause is unknown.', True)
    elif data.failure_code in SCHEMA_ERROR_CODES:
        category, cause, explanation, approval = (
            'INVALID_PAYLOAD', 'Input validation rejected the payload.',
            'The supplied validation code requires payload review; no automatic modification is authorized.', True)
    elif data.http_status == 429:
        category, cause, explanation, approval = (
            'RATE_LIMIT', 'Requests were throttled.', 'HTTP 429 indicates rate limiting; the exact quota is unknown.', False)
    elif data.http_status == 503:
        category, cause, explanation, approval = (
            'SERVICE_UNAVAILABLE', 'The service reported unavailability.',
            'HTTP 503 indicates unavailability; the underlying outage cause is unknown.', False)
    elif data.failure_code in CONNECTION_TIMEOUT_CODES and data.http_status in {None, 408, 504}:
        category, cause, explanation, approval = (
            'TIMEOUT', 'A connection timed out.',
            'The structured connection-timeout code indicates an expired connection wait; network cause is unknown.', False)
    else:
        return None
    return Diagnosis(
        failure_category=category, root_cause=cause, explanation=explanation,
        recommended_action='ESCALATE' if approval else 'RETRY_WITH_BACKOFF',
        confidence=0.99, requires_human_approval=approval,
        alternative_actions=['ESCALATE'] if approval else ['USE_APPROVED_FALLBACK', 'ESCALATE'],
    )
