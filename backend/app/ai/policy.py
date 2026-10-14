from dataclasses import dataclass

from app.ai.schemas import Diagnosis, DiagnosisInput


@dataclass(frozen=True)
class PolicyDecision:
    recovery_category: str = 'UNKNOWN_FAILURE'
    allow_fallback: bool = False
    reason: str = 'AI_POLICY_ESCALATE'


def evaluate_policy(data: DiagnosisInput, diagnosis: Diagnosis, threshold: float) -> PolicyDecision:
    # Independent evidence and allowlists constrain the model; confidence alone grants nothing.
    if diagnosis.requires_human_approval:
        return PolicyDecision(reason='AI_HUMAN_APPROVAL_REQUIRED')
    if diagnosis.confidence < threshold:
        return PolicyDecision(reason='AI_LOW_CONFIDENCE')
    if diagnosis.recommended_action == 'ESCALATE':
        return PolicyDecision()
    if data.failure_code in {'AUTHENTICATION_FAILURE', 'INVALID_PAYLOAD', 'SCHEMA_VALIDATION_ERROR'} or data.http_status in {400, 401, 403, 422}:
        return PolicyDecision(reason='AI_UNSAFE_EVIDENCE')
    categories = {'NETWORK_ERROR', 'TIMEOUT', 'SERVICE_UNAVAILABLE', 'RATE_LIMIT'}
    safe_codes = {'TRANSIENT_NETWORK_FAILURE', 'NETWORK_RETRY_SUCCESS', 'PROVIDER_UNAVAILABLE',
                  'NETWORK_FALLBACK_SUCCESS', 'NETWORK_BOTH_FAIL', 'NETWORK_VERIFY_FAIL',
                  'RATE_LIMIT', 'TIMEOUT', 'NETWORK_ERROR', 'SERVICE_UNAVAILABLE', 'CONNECTION_TIMEOUT', 'CONNECT_TIMEOUT'}
    safe_status = data.http_status in {408, 429, 500, 502, 503, 504}
    if diagnosis.failure_category not in categories or (data.failure_code not in safe_codes and not safe_status):
        return PolicyDecision(reason='AI_INSUFFICIENT_EVIDENCE')
    category = 'RATE_LIMIT' if diagnosis.failure_category == 'RATE_LIMIT' else 'TRANSIENT_NETWORK_FAILURE'
    fallback = diagnosis.recommended_action == 'USE_APPROVED_FALLBACK' or 'USE_APPROVED_FALLBACK' in diagnosis.alternative_actions
    return PolicyDecision(category, fallback, 'AI_POLICY_ACCEPTED')
