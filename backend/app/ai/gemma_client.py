"""Official Google SDK, explicit hosted Gemma models, fixed-code failures."""
from typing import Protocol

import httpx

from app.ai.prompts import SYSTEM_PROMPT, diagnosis_prompt
from app.ai.schemas import DiagnosisInput

# Verified in Google documentation and with the configured key's model listing.
SUPPORTED_GEMMA_MODELS = frozenset({'gemma-4-26b-a4b-it', 'gemma-4-31b-it'})


class ProviderFailure(Exception):
    CODES = frozenset({'AI_TIMEOUT', 'AI_AUTHENTICATION_FAILED', 'AI_RATE_LIMITED',
                       'AI_UNAVAILABLE', 'AI_MODEL_UNSUPPORTED', 'AI_KEY_MISSING',
                       'AI_SDK_MISSING', 'AI_INVALID_OUTPUT', 'AI_UNSAFE_OUTPUT'})

    VALIDATION_CODES = frozenset({
        'AI_OUTPUT_JSON_SYNTAX', 'AI_OUTPUT_MISSING_FIELDS', 'AI_OUTPUT_TYPE_ERROR',
        'AI_OUTPUT_ENUM_ERROR', 'AI_OUTPUT_CONFIDENCE_ERROR', 'AI_OUTPUT_EXTRA_FIELDS',
        'AI_OUTPUT_FORMATTING', 'AI_OUTPUT_DUPLICATE_KEYS', 'AI_OUTPUT_LIMIT',
        'AI_OUTPUT_UNSAFE_TEXT', 'AI_OUTPUT_NOT_OBJECT', 'AI_OUTPUT_SCHEMA_ERROR',
        'AI_OUTPUT_NO_TEXT', 'AI_OUTPUT_EMPTY', 'AI_OUTPUT_TOKEN_LIMIT',
    })

    def __init__(self, code, *, validation_codes=(), validation_fields=()):
        from app.ai.schemas import Diagnosis
        self.code = code if code in self.CODES else 'AI_UNAVAILABLE'
        self.validation_codes = tuple(sorted(set(validation_codes) & self.VALIDATION_CODES))
        self.validation_fields = tuple(sorted(set(validation_fields) & set(Diagnosis.model_fields)))
        super().__init__(self.code)


class DiagnosisProvider(Protocol):
    model_id: str

    def generate(self, data: DiagnosisInput) -> str: ...


class GemmaProvider:
    def __init__(self, settings):
        self.settings = settings
        self.model_id = settings.ai_model

    def generate(self, data: DiagnosisInput, *, timeout_seconds: float | None = None) -> str:
        if self.model_id not in SUPPORTED_GEMMA_MODELS:
            raise ProviderFailure('AI_MODEL_UNSUPPORTED')
        key = self.settings.gemini_api_key.get_secret_value()
        if not key:
            raise ProviderFailure('AI_KEY_MISSING')
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise ProviderFailure('AI_SDK_MISSING') from None
        try:
            with genai.Client(api_key=key, vertexai=False, http_options=types.HttpOptions(
                api_version='v1beta', base_url='https://generativelanguage.googleapis.com',
                timeout=int(min(self.settings.ai_timeout_seconds,
                                max(1, timeout_seconds) if timeout_seconds is not None else 60) * 1000),
                retry_options=types.HttpRetryOptions(attempts=1),
                client_args={'trust_env': False}, async_client_args={'trust_env': False},
            )) as client:
                response = client.models.generate_content(
                    model=self.model_id, contents=diagnosis_prompt(data),
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT, temperature=0,
                        max_output_tokens=self.settings.ai_max_output_tokens,
                        thinking_config=(types.ThinkingConfig(thinking_level=self.settings.ai_thinking_level)
                                         if self.settings.ai_thinking_level != 'default' else None),
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    ),
                )
                text = response.text
                token_limited = any(str(getattr(candidate.finish_reason, 'value', candidate.finish_reason)) == 'MAX_TOKENS'
                                    for candidate in (response.candidates or []))
            if token_limited:
                raise ProviderFailure('AI_INVALID_OUTPUT', validation_codes=('AI_OUTPUT_TOKEN_LIMIT',))
            if not isinstance(text, str):
                raise ProviderFailure('AI_INVALID_OUTPUT', validation_codes=('AI_OUTPUT_NO_TEXT',))
            if not text.strip():
                raise ProviderFailure('AI_INVALID_OUTPUT', validation_codes=('AI_OUTPUT_EMPTY',))
            if len(text) > 8192:
                raise ProviderFailure('AI_INVALID_OUTPUT', validation_codes=('AI_OUTPUT_LIMIT',))
            if key in text:
                raise ProviderFailure('AI_UNSAFE_OUTPUT')
            return text
        except ProviderFailure:
            raise
        except (TimeoutError, httpx.TimeoutException):
            raise ProviderFailure('AI_TIMEOUT') from None
        except Exception as exc:
            code = getattr(exc, 'code', None)
            fixed = {401: 'AI_AUTHENTICATION_FAILED', 403: 'AI_AUTHENTICATION_FAILED',
                     429: 'AI_RATE_LIMITED', 408: 'AI_TIMEOUT', 504: 'AI_TIMEOUT'}.get(code, 'AI_UNAVAILABLE')
            raise ProviderFailure(fixed) from None
