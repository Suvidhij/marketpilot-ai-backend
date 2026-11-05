from alembic import context
from sqlalchemy import create_engine, pool
from app.core.config import get_settings
from app.core.database import Base
from app import models  # register metadata

config = context.config
target_metadata = Base.metadata
url = get_settings().database_url

if context.is_offline_mode():
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        if url.startswith("sqlite"):
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=url.startswith("sqlite"),
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
