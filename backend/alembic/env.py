from alembic import context
from sqlalchemy import text

from app.core.config import Settings
from app.core.database import Base, make_engine
from app.models import entities  # noqa: F401

target_metadata = Base.metadata
url = Settings().database_url.get_secret_value()

if context.is_offline_mode():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    supplied_connection = context.config.attributes.get("connection")
    if supplied_connection is not None:
        required_schema = context.config.attributes.get('required_schema')
        if required_schema is not None:
            if not required_schema.startswith('test_') or supplied_connection.scalar(text('SELECT current_schema()')) != required_schema:
                raise RuntimeError('Migration refused: isolated test schema is not active.')
        context.configure(connection=supplied_connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    else:
        engine = make_engine(url)
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
        engine.dispose()
