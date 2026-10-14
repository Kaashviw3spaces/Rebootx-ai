"""Local deterministic diagnosis+policy benchmark. No SDK/network/DB calls."""
from datetime import datetime, timezone
import json
from statistics import median
from time import perf_counter_ns

from app.ai.diagnosis import DiagnosisEngine
from app.ai.schemas import DiagnosisInput
from app.core.config import Settings


class NoModelCalls:
    model_id = 'not-used'

    def generate(self, _):
        raise AssertionError('Benchmark must never call a model')


def main():
    settings = Settings(_env_file=None, ai_provider='gemma', ai_fast_path_enabled=True,
                        ai_min_confidence=0.75, gemini_api_key='')
    engine = DiagnosisEngine(settings, NoModelCalls())
    cases = [('HTTP_429', 'UNKNOWN_FAILURE', 429), ('HTTP_401', 'UNKNOWN_FAILURE', 401),
             ('HTTP_503', 'UNKNOWN_FAILURE', 503), ('CONNECTION_TIMEOUT', 'CONNECTION_TIMEOUT', None),
             ('SCHEMA_VALIDATION_ERROR', 'SCHEMA_VALIDATION_ERROR', None)]
    results = []
    for name, code, status in cases:
        data = DiagnosisInput(failure_code=code, failure_timestamp=datetime.now(timezone.utc), http_status=status)
        for _ in range(100):
            assert engine.diagnose(data).source == 'deterministic'
        durations = []
        for _ in range(2000):
            start = perf_counter_ns()
            outcome = engine.diagnose(data)
            durations.append((perf_counter_ns() - start) / 1_000_000)
            assert outcome.source == 'deterministic'
        durations.sort()
        results.append({'case': name, 'samples': len(durations), 'median_ms': round(median(durations), 6),
                        'p95_ms': round(durations[int(len(durations) * 0.95) - 1], 6)})
    print(json.dumps({'measurement': 'local deterministic classification + Pydantic + policy only',
                      'hosted_inference': False, 'database_or_temporal_included': False,
                      'results': results}, indent=2))


if __name__ == '__main__':
    main()
