import asyncio
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from temporalio.testing import ActivityEnvironment

from app.ai.diagnosis import DiagnosisEngine, parse_diagnosis
from app.ai.gemma_client import GemmaProvider, ProviderFailure
from app.ai.prompts import diagnosis_prompt
from app.ai.schemas import Diagnosis
from app.models.entities import AuditLog
from app.temporal.activities import RecoveryActivities
from app.temporal.schemas import StepRequest, StepResult
from app.temporal.workflows import IncidentRecoveryWorkflow
from test_ai import FakeProvider, evidence, output, settings
from test_recovery import create_incident


@pytest.mark.parametrize('field', ['explanation', 'requires_human_approval', 'alternative_actions'])
def test_missing_production_fields_are_classified_without_filling(field):
    data = json.loads(output())
    del data[field]
    with pytest.raises(ProviderFailure) as exc:
        parse_diagnosis(json.dumps(data))
    assert exc.value.code == 'AI_INVALID_OUTPUT'
    assert exc.value.validation_codes == ('AI_OUTPUT_MISSING_FIELDS',)
    assert exc.value.validation_fields == (field,)


@pytest.mark.parametrize('raw,code,fields', [
    ('{"failure_category":', 'AI_OUTPUT_JSON_SYNTAX', ()),
    ('```json\n' + output() + '\n```', 'AI_OUTPUT_FORMATTING', ()),
    ('Here is JSON: ' + output(), 'AI_OUTPUT_FORMATTING', ()),
    (output() + '\nAdditional explanation', 'AI_OUTPUT_FORMATTING', ()),
    ('[]', 'AI_OUTPUT_NOT_OBJECT', ()),
    (output(failure_category='unsupported-private-value'), 'AI_OUTPUT_ENUM_ERROR', ('failure_category',)),
    (output(recommended_action='EXECUTE_CODE'), 'AI_OUTPUT_ENUM_ERROR', ('recommended_action',)),
    (output(confidence='0.9'), 'AI_OUTPUT_TYPE_ERROR', ('confidence',)),
    (output(confidence=1.1), 'AI_OUTPUT_CONFIDENCE_ERROR', ('confidence',)),
    (output(confidence=float('nan')), 'AI_OUTPUT_CONFIDENCE_ERROR', ('confidence',)),
    (output(requires_human_approval='false'), 'AI_OUTPUT_TYPE_ERROR', ('requires_human_approval',)),
    (output(extra='private-value'), 'AI_OUTPUT_EXTRA_FIELDS', ()),
    (output(root_cause='password=private-value'), 'AI_OUTPUT_UNSAFE_TEXT', ('root_cause',)),
    (output().replace('"confidence": 0.94', '"confidence": 0.94, "confidence": 1'), 'AI_OUTPUT_DUPLICATE_KEYS', ()),
])
def test_validation_details_are_fixed_codes_and_allowlisted_names(raw, code, fields):
    with pytest.raises(ProviderFailure) as exc:
        parse_diagnosis(raw)
    assert exc.value.validation_codes == (code,)
    assert exc.value.validation_fields == fields
    assert 'private-value' not in str(exc.value)
    assert exc.value.__suppress_context__


def test_untrusted_extra_key_is_not_used_as_diagnostic_field_name():
    data = json.loads(output())
    data['customer-sensitive-extra-key'] = 'private-value'
    with pytest.raises(ProviderFailure) as exc:
        parse_diagnosis(json.dumps(data))
    assert exc.value.validation_codes == ('AI_OUTPUT_EXTRA_FIELDS',)
    assert exc.value.validation_fields == ()


def test_production_prompt_contract_and_example_match_strict_schema():
    prompt = diagnosis_prompt(evidence())
    contract = json.loads(prompt.split('\n', 1)[1])
    schema = contract['schema']
    original = Diagnosis.model_json_schema()
    assert schema['required'] == original['required']
    assert schema['additionalProperties'] is False
    for field in original['properties']:
        assert {k: v for k, v in original['properties'][field].items() if k != 'title'} == schema['properties'][field]
    assert parse_diagnosis(json.dumps(contract['synthetic_example_only_do_not_copy']))
    assert contract['untrusted_evidence']['failure'] == evidence().error_message


@pytest.mark.parametrize('patched', [False, True])
def test_diagnosis_timeout_hierarchy_and_legacy_branch(monkeypatch, patched):
    calls = []
    async def execute(_, request, **kwargs):
        calls.append((request.operation, kwargs))
        return StepResult('NEEDS_ATTENTION' if request.operation == 'escalate' else 'DIAGNOSING', 'UNKNOWN_FAILURE')
    monkeypatch.setattr('app.temporal.workflows.workflow.execute_activity', execute)
    monkeypatch.setattr('app.temporal.workflows.workflow.patched', lambda _: patched)
    asyncio.run(IncidentRecoveryWorkflow().run(SimpleNamespace()))
    for operation, options in calls:
        start = options['start_to_close_timeout'].total_seconds()
        schedule = options['schedule_to_close_timeout'].total_seconds()
        if operation == 'diagnose' and patched:
            assert start > settings().ai_timeout_seconds
            assert schedule >= start * options['retry_policy'].maximum_attempts + 10
            assert (start, schedule) == (75, 240)
        else:
            assert (start, schedule) == (30, 120)


@pytest.mark.parametrize('seconds,cap,expected_ms', [(60, None, 60000), (10, None, 10000), (60, 20, 20000)])
def test_sdk_timeout_honors_configuration_and_legacy_activity_cap(monkeypatch, seconds, cap, expected_ms):
    from google import genai
    class Client:
        def __init__(self, **kwargs):
            assert kwargs['http_options'].timeout == expected_ms
            assert kwargs['http_options'].retry_options.attempts == 1
            self.models = self
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def generate_content(self, **kwargs):
            assert kwargs['config'].thinking_config is None
            assert kwargs['config'].tools is None and kwargs['config'].automatic_function_calling.disable
            return SimpleNamespace(text=output(), candidates=[])
    monkeypatch.setattr(genai, 'Client', Client)
    assert GemmaProvider(settings(ai_timeout_seconds=seconds)).generate(evidence(), timeout_seconds=cap)


@pytest.mark.parametrize('seconds', [0, 61, float('nan'), float('inf')])
def test_ai_timeout_is_bounded(seconds):
    with pytest.raises(ValidationError):
        settings(ai_timeout_seconds=seconds)


def test_validation_failure_audit_details_are_persisted_and_idempotent(context):
    data = create_incident(context, 'RATE_LIMIT')
    incomplete = json.loads(output())
    del incomplete['requires_human_approval']
    provider = FakeProvider(json.dumps(incomplete))
    config = settings()
    activities = RecoveryActivities(context[1], config, DiagnosisEngine(config, provider))
    env = ActivityEnvironment()
    env.run(activities.step, StepRequest(data, 'accept'))
    first = env.run(activities.step, StepRequest(data, 'diagnose'))
    assert env.run(activities.step, StepRequest(data, 'diagnose')) == first
    assert len(provider.calls) == 1
    with context[1]() as db:
        audit = db.scalar(select(AuditLog).where(AuditLog.logical_key == 'recovery:v1:diagnose'))
        assert audit.redacted_details['diagnosis']['validation_codes'] == ['AI_OUTPUT_MISSING_FIELDS']
        assert audit.redacted_details['diagnosis']['validation_fields'] == ['requires_human_approval']
        assert audit.redacted_details['diagnosis']['fallback_reason'] == 'AI_INVALID_OUTPUT'


@pytest.mark.parametrize('text,finish,code', [
    (None, 'STOP', 'AI_OUTPUT_NO_TEXT'), ('', 'STOP', 'AI_OUTPUT_EMPTY'),
    ('   ', 'STOP', 'AI_OUTPUT_EMPTY'), ('x' * 8193, 'STOP', 'AI_OUTPUT_LIMIT'),
    ('', 'MAX_TOKENS', 'AI_OUTPUT_TOKEN_LIMIT'),
])
def test_sdk_output_envelope_failures_are_classified_without_raw_output(monkeypatch, text, finish, code):
    from google import genai
    class Client:
        def __init__(self, **kwargs): self.models = self
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def generate_content(self, **kwargs):
            return SimpleNamespace(text=text, candidates=[SimpleNamespace(finish_reason=finish)])
    monkeypatch.setattr(genai, 'Client', Client)
    with pytest.raises(ProviderFailure) as exc:
        GemmaProvider(settings()).generate(evidence())
    assert exc.value.code == 'AI_INVALID_OUTPUT'
    assert exc.value.validation_codes == (code,)
    assert exc.value.validation_fields == ()
