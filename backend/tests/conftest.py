import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.core.database import make_engine, session_factory
from app.core.security import token_hash
from app.main import create_app
from app.models.entities import Integration, Tenant, Workflow


@pytest.fixture
def context(tmp_path, monkeypatch, request):
    # PostgreSQL uses an isolated schema; never delete existing application tables.
    url = os.environ.get('TEST_DATABASE_URL', f'sqlite:///{tmp_path / "test.db"}')
    parsed = make_url(url)
    if parsed.host and '-pooler.' in parsed.host:
        pytest.fail('Schema tests require a direct connection; use scripts.test_postgres.', pytrace=False)
    engine = make_engine(url)
    schema = None
    schema_created = False
    def cleanup():
        try:
            if schema_created:
                with engine.begin() as connection:
                    connection.exec_driver_sql(f'DROP SCHEMA {schema} CASCADE')
        finally:
            engine.dispose()
    request.addfinalizer(cleanup)
    if engine.dialect.name == 'postgresql':
        schema = 'test_' + uuid4().hex
        with engine.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA {schema}')
        schema_created = True
        engine.dispose()
        from sqlalchemy import event
        @event.listens_for(engine, 'connect')
        def search_path(connection, _):
            previous = connection.autocommit
            connection.autocommit = True
            with connection.cursor() as cursor:
                cursor.execute(f'SET search_path TO {schema}')
            connection.autocommit = previous
    monkeypatch.setenv('DATABASE_URL', url)
    config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    if schema:
        config.attributes['required_schema'] = schema
    # Share the isolated engine with migrations via the standard config attribute.
    with engine.begin() as connection:
        if schema:
            assert connection.scalar(text('SELECT current_schema()')) == schema
        config.attributes['connection'] = connection
        command.upgrade(config, 'head')
    sessions = session_factory(engine)
    ids = []
    tokens = []
    for index in range(2):
        secret_ref = f'TEST_WEBHOOK_{index}'
        monkeypatch.setenv(secret_ref, f'synthetic-webhook-secret-{index}-' + 'x' * 32)
        token = f'synthetic-read-token-{index}-' + 'y' * 32
        with sessions() as db:
            tenant = Tenant(name=f'Demo {index}', read_token_hash=token_hash(token))
            db.add(tenant)
            db.flush()
            integration = Integration(tenant_id=tenant.id, kind='n8n', secret_ref=secret_ref)
            db.add(integration)
            db.flush()
            db.add(Workflow(tenant_id=tenant.id, integration_id=integration.id, external_id='notify-orders'))
            db.commit()
            ids.append(str(integration.id))
            tokens.append(token)
    app = create_app(Settings(database_url=url), engine=engine)
    with TestClient(app) as client:
        yield client, sessions, ids, tokens, engine, config

