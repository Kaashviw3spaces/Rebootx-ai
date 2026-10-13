"""Run existing tests in isolated PostgreSQL schemas without logging credentials."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from dotenv import dotenv_values
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.core.database import make_engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--use-development-database', action='store_true')
    args = parser.parse_args()
    engine = None
    try:
        settings = Settings()
        raw = os.environ.get('TEST_DATABASE_URL')
        if not raw:
            if not args.use_development_database or settings.app_env != 'development':
                print('Set TEST_DATABASE_URL or use --use-development-database with APP_ENV=development.')
                return 1
            raw = settings.database_url.get_secret_value()
        url = make_url(raw)
        if url.drivername != 'postgresql+psycopg':
            print('Tests require postgresql+psycopg (Psycopg 3).')
            return 1
        if url.host and url.host.endswith('.neon.tech'):
            if url.query.get('sslmode') not in {'require', 'verify-ca', 'verify-full'}:
                print('Neon tests require SSL.')
                return 1
            # Isolated fixtures rely on session-level SET search_path. Neon
            # transaction pooling cannot preserve that state between transactions.
            url = url.set(host=url.host.replace('-pooler.', '.'))
        url = url.update_query_dict({'connect_timeout': '15'})
        engine = make_engine(url)
        with engine.connect() as connection:
            connection.exec_driver_sql('SELECT 1')
        env = os.environ.copy()
        env['TEST_DATABASE_URL'] = url.render_as_string(hide_password=False)
        print('Running PostgreSQL suite in randomly named test schemas (direct connection).', flush=True)
        # Avoid reusing pytest directories created under a different Windows
        # sandbox identity. Only this newly allocated temporary directory is removed.
        with tempfile.TemporaryDirectory(prefix='rebootx-postgres-tests-') as temporary:
            result = subprocess.run(
                [sys.executable, '-m', 'pytest', '-q', '--tb=short', '-p', 'no:cacheprovider',
                 '--basetemp', str(Path(temporary) / 'pytest')], env=env,
                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
            )
        output = result.stdout + result.stderr
        secrets = [raw, env['TEST_DATABASE_URL'], url.password, url.username, url.host, url.database]
        secrets.extend(value for key, value in dotenv_values('.env').items()
                       if value and ('SECRET' in key or 'TOKEN' in key or key.endswith('DATABASE_URL')))
        for secret in sorted((value for value in secrets if value), key=len, reverse=True):
            output = output.replace(secret, '[REDACTED]')
        output = re.sub(r'postgres(?:ql)?(?:\+\w+)?://[^\s\'\"]+', '[REDACTED DATABASE URL]', output)
        print(output, end='')
        return result.returncode
    except Exception as exc:
        print('PostgreSQL test runner failed:', type(exc).__name__, '(details suppressed to protect secrets)')
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
