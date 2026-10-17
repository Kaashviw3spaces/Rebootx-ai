"""Supported public API only. Never retry a mutation or log provider payloads."""
import hashlib
import json
import re
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, StrictStr, ValidationError
from typing import Literal


class N8nError(Exception):
    """A fixed, secret-free error code."""


class Execution(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: StrictStr
    workflowId: StrictStr
    status: Literal['canceled', 'crashed', 'error', 'new', 'running', 'success', 'unknown', 'waiting']
    retryOf: StrictStr | None
    retrySuccessId: StrictStr | None = None


def workflow_fingerprint(workflow):
    # Pin the entire saved snapshot, including Code/HTTP nodes and credentials references.
    return hashlib.sha256(json.dumps(workflow, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


class N8nClient:
    def __init__(self, settings, transport=None):
        url = urlsplit(settings.n8n_base_url)
        if (url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.path not in {'', '/'}
                or (url.scheme == 'http' and url.hostname not in {'localhost', '127.0.0.1', '::1'})):
            raise N8nError('N8N_INVALID_BASE_URL')
        if not settings.n8n_api_key.get_secret_value():
            raise N8nError('N8N_MISSING_CREDENTIALS')
        if settings.n8n_supported_version != '2.43.6':
            raise N8nError('N8N_UNSUPPORTED_VERSION')
        self.http = httpx.Client(base_url=settings.n8n_base_url.rstrip('/') + '/api/v1/',
            headers={'X-N8N-API-KEY': settings.n8n_api_key.get_secret_value()},
            timeout=httpx.Timeout(settings.n8n_read_timeout, connect=settings.n8n_connect_timeout),
            follow_redirects=False, trust_env=False, transport=transport)

    def close(self):
        self.http.close()

    def request(self, method, path, **kwargs):
        # Bounded to one HTTP attempt. Temporal may redeliver reads; the action ledger fences POSTs.
        try:
            response = self.http.request(method, path, **kwargs)
        except httpx.TimeoutException:
            raise N8nError('N8N_NETWORK_TIMEOUT') from None
        except httpx.HTTPError:
            raise N8nError('N8N_NETWORK_FAILURE') from None
        if response.status_code != 200:
            code = {401: 'AUTHENTICATION', 403: 'FORBIDDEN', 404: 'NOT_FOUND', 429: 'RATE_LIMIT',
                    500: 'SERVER_ERROR', 503: 'UNAVAILABLE'}.get(response.status_code, 'HTTP_FAILURE')
            raise N8nError('N8N_' + code)
        try:
            data = response.json()
        except ValueError:
            raise N8nError('N8N_MALFORMED_RESPONSE') from None
        if not isinstance(data, dict):
            raise N8nError('N8N_MALFORMED_RESPONSE')
        return data

    @staticmethod
    def execution_id(value):
        if not isinstance(value, str) or not re.fullmatch(r'[1-9][0-9]{0,19}', value):
            raise N8nError('N8N_INVALID_EXECUTION_ID')
        return value

    def parse(self, data, workflow_id, execution_id=None, retry_of=None):
        try:
            result = Execution.model_validate(data)
        except ValidationError:
            raise N8nError('N8N_MALFORMED_RESPONSE') from None
        self.execution_id(result.id)
        if result.workflowId != workflow_id or (execution_id and result.id != execution_id):
            raise N8nError('N8N_EXECUTION_IDENTITY_MISMATCH')
        if retry_of and (result.retryOf != retry_of or result.id == retry_of):
            raise N8nError('N8N_RETRY_IDENTITY_MISMATCH')
        return result

    def inspect(self, execution_id, workflow_id, *, retry_of=None, fingerprint=None):
        execution_id = self.execution_id(execution_id)
        data = self.request('GET', f'executions/{execution_id}', params={'includeData': 'true' if fingerprint else 'false'})
        result = self.parse(data, workflow_id, execution_id, retry_of)
        if fingerprint and (not isinstance(data.get('workflowData'), dict)
                            or workflow_fingerprint(data['workflowData']) != fingerprint):
            raise N8nError('N8N_WORKFLOW_SNAPSHOT_NOT_AUTHORIZED')
        return result

    def retry(self, execution_id, workflow_id):
        execution_id = self.execution_id(execution_id)
        data = self.request('POST', f'executions/{execution_id}/retry', json={'loadWorkflow': False})
        return self.parse(data, workflow_id, retry_of=execution_id)
