"""Check PostgreSQL without printing credentials; optionally migrate an empty dev DB."""
import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.core.database import make_engine


class DatabaseCheckError(Exception):
    """An operator-safe diagnostic, never a raw driver/settings error."""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    migration = parser.add_mutually_exclusive_group()
    migration.add_argument('--migrate-empty-dev', action='store_true')
    migration.add_argument('--upgrade-dev', action='store_true', help='Apply reviewed additive upgrades to 0003')
    args = parser.parse_args()
    engine = None
    try:
        settings = Settings()
        url = make_url(settings.database_url.get_secret_value())
        if url.drivername != 'postgresql+psycopg':
            raise DatabaseCheckError('Use the postgresql+psycopg URL scheme (Psycopg 3).')
        neon = bool(url.host and url.host.endswith('.neon.tech'))
        if neon and url.query.get('sslmode') not in {'require', 'verify-ca', 'verify-full'}:
            raise DatabaseCheckError('Neon requires sslmode=require or certificate verification.')
        if not (url.host and url.username and url.password and url.database):
            raise DatabaseCheckError('Database URL must include host, username, password, and database.')
        print('Configuration: PostgreSQL / Psycopg 3; Neon:', neon)
        engine = make_engine(url.update_query_dict({'connect_timeout': '15'}))
        config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
        head = ScriptDirectory.from_config(config).get_current_head()
        with engine.begin() as connection:
            if connection.scalar(text('SELECT 1')) != 1:
                raise DatabaseCheckError('SELECT 1 returned an unexpected result.')
            print('SELECT 1: passed')
            # Neon terminates TLS at its proxy, so pg_stat_ssl describes the
            # proxy-to-Postgres hop. Inspect the actual client libpq connection.
            tls = connection.connection.driver_connection.pgconn.ssl_in_use
            print('TLS active:', tls)
            if neon and tls is not True:
                raise DatabaseCheckError('Neon connection did not confirm TLS.')
            tables = set(inspect(connection).get_table_names(schema='public'))
            revision = None
            if 'alembic_version' in tables:
                revision = connection.scalar(text('SELECT version_num FROM public.alembic_version'))
            print('Public tables:', ', '.join(sorted(tables)) or '(none)')
            print('Migration revision:', revision or '(none)')
            if args.upgrade_dev and revision != head:
                if settings.app_env != 'development' or revision not in {'0001', '0002'} or head != '0003':
                    raise DatabaseCheckError('Upgrade refused: requires development database at 0001/0002 and head 0003.')
                if connection.scalar(text('SELECT current_schema()')) != 'public':
                    raise DatabaseCheckError('Upgrade refused: default schema must be public.')
                baseline = {'tenants', 'integrations', 'workflows', 'incidents', 'audit_logs', 'recovery_attempts'}
                if revision == '0002':
                    baseline.add('recovery_outbox')
                if not baseline <= tables or 'incident_diagnoses' in tables or (revision == '0001' and 'recovery_outbox' in tables):
                    raise DatabaseCheckError('Upgrade refused: unexpected baseline tables; review manually.')
                config.attributes['connection'] = connection
                command.upgrade(config, 'head')
                print('Migration: applied reviewed additive upgrade to 0003')
            if args.migrate_empty_dev and revision != head:
                if settings.app_env != 'development':
                    raise DatabaseCheckError('Migration refused: APP_ENV must be development.')
                objects = connection.scalar(text("""
                    SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
                    AND n.nspname NOT LIKE 'pg_toast%' AND n.nspname NOT LIKE 'pg_temp%'
                """))
                if objects:
                    raise DatabaseCheckError('Migration refused: database contains existing user objects; review manually.')
                if connection.scalar(text('SELECT current_schema()')) != 'public':
                    raise DatabaseCheckError('Migration refused: default schema must be public.')
                config.attributes['connection'] = connection
                command.upgrade(config, 'head')
                print('Migration: applied existing upgrade to head')
            if args.migrate_empty_dev or args.upgrade_dev or revision == head:
                expected = {'tenants', 'integrations', 'workflows', 'incidents', 'audit_logs', 'recovery_attempts', 'recovery_outbox', 'incident_diagnoses', 'alembic_version'}
                tables = set(inspect(connection).get_table_names(schema='public'))
                if not expected <= tables:
                    raise DatabaseCheckError('Expected application tables are missing.')
                config.attributes['connection'] = connection
                command.check(config)
                print('Verified tables:', ', '.join(sorted(expected)))
                print('Migration/model compatibility: passed')
        return 0
    except DatabaseCheckError as exc:
        print(str(exc))
        return 1
    except Exception as exc:
        # Driver exceptions can contain connection strings, hosts, or SQL parameters.
        print('Database check failed:', type(exc).__name__, '(details suppressed to protect secrets)')
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
