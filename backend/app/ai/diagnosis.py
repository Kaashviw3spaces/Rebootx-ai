"""Validate provider output and decide safe fallback without logging raw output."""
from dataclasses import dataclass
import json

from pydantic import ValidationError

from app.ai.gemma_client import GemmaProvider, ProviderFailure
from app.ai.fast_path import classify_structured_failure
from app.ai.policy import PolicyDecision, evaluate_policy
from app.ai.schemas import Diagnosis, DiagnosisInput


@dataclass(frozen=True)
class DiagnosisOutcome:
    diagnosis: Diagnosis
    status: str
    model_id: str
    fallback_reason: str | None
    policy: PolicyDecision
    validation_codes: tuple[str, ...] = ()
    validation_fields: tuple[str, ...] = ()
    source: str = 'gemma'


def mock_diagnosis(data: DiagnosisInput) -> Diagnosis:
    category = {
        'RATE_LIMIT': 'RATE_LIMIT', 'AUTHENTICATION_FAILURE': 'AUTHENTICATION_ERROR',
        'INVALID_PAYLOAD': 'INVALID_PAYLOAD', 'TIMEOUT': 'TIMEOUT',
        'SERVICE_UNAVAILABLE': 'SERVICE_UNAVAILABLE', 'PROVIDER_UNAVAILABLE': 'SERVICE_UNAVAILABLE',
        'TRANSIENT_NETWORK_FAILURE': 'NETWORK_ERROR', 'NETWORK_ERROR': 'NETWORK_ERROR',
        'NETWORK_RETRY_SUCCESS': 'NETWORK_ERROR', 'NETWORK_FALLBACK_SUCCESS': 'NETWORK_ERROR',
        'NETWORK_BOTH_FAIL': 'NETWORK_ERROR', 'NETWORK_VERIFY_FAIL': 'NETWORK_ERROR',
    }.get(data.failure_code, 'UNKNOWN_ERROR')
    unsafe = category in {'AUTHENTICATION_ERROR', 'INVALID_PAYLOAD', 'UNKNOWN_ERROR'}
    return Diagnosis(failure_category=category, root_cause='Deterministic classification from the supplied failure code.',
                     explanation='Mock diagnosis; no AI inference or external completion evidence.',
                     recommended_action='ESCALATE' if unsafe else 'RETRY_WITH_BACKOFF', confidence=0.0 if category == 'UNKNOWN_ERROR' else 1.0,
                     requires_human_approval=unsafe, alternative_actions=['ESCALATE'] if unsafe else ['USE_APPROVED_FALLBACK', 'ESCALATE'])


def parse_diagnosis(text: str) -> Diagnosis:
    class DuplicateKey(ValueError):
        pass

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise DuplicateKey()
            result[key] = value
        return result
    def fail(detail, fields=()):
        raise ProviderFailure('AI_INVALID_OUTPUT', validation_codes=(detail,), validation_fields=fields) from None

    if not isinstance(text, str) or len(text) > 8192:
        fail('AI_OUTPUT_LIMIT')
    stripped = text.strip()
    if stripped.startswith('```') or ('{' in stripped and not stripped.startswith(('{', '['))):
        fail('AI_OUTPUT_FORMATTING')
    try:
        payload = json.loads(text, object_pairs_hook=unique)
    except DuplicateKey:
        fail('AI_OUTPUT_DUPLICATE_KEYS')
    except json.JSONDecodeError as exc:
        fail('AI_OUTPUT_FORMATTING' if exc.msg == 'Extra data' else 'AI_OUTPUT_JSON_SYNTAX')
    if not isinstance(payload, dict):
        fail('AI_OUTPUT_NOT_OBJECT')
    try:
        return Diagnosis.model_validate(payload)
    except ValidationError as exc:
        codes, fields = set(), set()
        for error in exc.errors(include_input=False, include_context=False, include_url=False):
            field = error['loc'][0] if error['loc'] else None
            if field in Diagnosis.model_fields:
                fields.add(field)
            kind = error['type']
            if kind == 'missing':
                code = 'AI_OUTPUT_MISSING_FIELDS'
            elif kind == 'extra_forbidden':
                code = 'AI_OUTPUT_EXTRA_FIELDS'
            elif kind == 'literal_error':
                code = 'AI_OUTPUT_ENUM_ERROR'
            elif kind.endswith('_type'):
                code = 'AI_OUTPUT_TYPE_ERROR'
            elif field == 'confidence':
                code = 'AI_OUTPUT_CONFIDENCE_ERROR'
            elif kind == 'value_error':
                code = 'AI_OUTPUT_UNSAFE_TEXT'
            else:
                code = 'AI_OUTPUT_SCHEMA_ERROR'
            codes.add(code)
        raise ProviderFailure('AI_INVALID_OUTPUT', validation_codes=codes, validation_fields=fields) from None


class DiagnosisEngine:
    def __init__(self, settings, provider=None):
        self.settings = settings
        self.provider = provider if provider is not None else GemmaProvider(settings)

    def diagnose(self, data: DiagnosisInput, *, timeout_seconds: float | None = None) -> DiagnosisOutcome:
        if self.settings.ai_provider == 'mock':
            diagnosis = mock_diagnosis(data)
            return DiagnosisOutcome(diagnosis, 'MOCK', 'mock-diagnosis-v1', None,
                                    evaluate_policy(data, diagnosis, self.settings.ai_min_confidence), source='mock')
        if self.settings.ai_fast_path_enabled:
            diagnosis = classify_structured_failure(data)
            if diagnosis is not None:
                policy = evaluate_policy(data, diagnosis, self.settings.ai_min_confidence)
                return DiagnosisOutcome(diagnosis, 'SUCCEEDED' if policy.reason == 'AI_POLICY_ACCEPTED' else 'POLICY_REJECTED',
                                        'deterministic-diagnosis-v1', None, policy, source='deterministic')
        try:
            raw = (self.provider.generate(data, timeout_seconds=timeout_seconds)
                   if isinstance(self.provider, GemmaProvider) else self.provider.generate(data))
            diagnosis = parse_diagnosis(raw)
            policy = evaluate_policy(data, diagnosis, self.settings.ai_min_confidence)
            return DiagnosisOutcome(diagnosis, 'SUCCEEDED' if policy.reason == 'AI_POLICY_ACCEPTED' else 'POLICY_REJECTED',
                                    self.settings.ai_model, None, policy)
        except ProviderFailure as exc:
            code = exc.code
            validation_codes, validation_fields = exc.validation_codes, exc.validation_fields
        except Exception:
            code = 'AI_UNAVAILABLE'
            validation_codes, validation_fields = (), ()
        diagnosis = mock_diagnosis(data)
        if self.settings.ai_fallback_enabled:
            return DiagnosisOutcome(diagnosis, 'FALLBACK', 'mock-diagnosis-v1', code,
                                    evaluate_policy(data, diagnosis, self.settings.ai_min_confidence),
                                    validation_codes, validation_fields, source='mock')
        return DiagnosisOutcome(diagnosis.model_copy(update={'recommended_action': 'ESCALATE', 'requires_human_approval': True}),
                                'FAILED', 'mock-diagnosis-v1', code, PolicyDecision(reason='AI_FALLBACK_DISABLED'),
                                validation_codes, validation_fields, source='mock')
