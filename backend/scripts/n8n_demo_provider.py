"""Loopback-only disposable demo provider. No external calls or durable side effects.

Run: python -m uvicorn scripts.n8n_demo_provider:app --host 127.0.0.1 --port 8011
The first request for a run UUID fails; subsequent requests return a fixed success.
"""
from threading import Lock
from uuid import UUID
from fastapi import FastAPI, HTTPException, Request

app = FastAPI(title='REBOOTX controlled recovery demonstration')
seen = set()
guard = Lock()


@app.post('/probe/{run_id}')
def probe(run_id: UUID, request: Request):
    if request.client.host not in {'127.0.0.1', '::1', 'testclient'}:
        raise HTTPException(403, 'Loopback only')
    with guard:
        if run_id not in seen:
            if len(seen) >= 1000:
                raise HTTPException(503, 'Restart this disposable demo provider')
            seen.add(run_id)
            raise HTTPException(503, 'Controlled first-attempt failure')
    return {'status': 'success', 'run_id': str(run_id), 'side_effects': 'none'}
