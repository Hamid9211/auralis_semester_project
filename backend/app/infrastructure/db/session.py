"""Engine and session factory creation (the only place that knows the DB driver)."""

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_IN_MEMORY_URLS = ("sqlite://", "sqlite:///:memory:")


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    # SQLite ignores FOREIGN KEY constraints unless this pragma is set per connection.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_engine(database_url: str) -> Engine:
    """Create an engine; in-memory SQLite shares one connection so tests see one DB."""
    kwargs: dict = {}
    if database_url.startswith("sqlite"):
        # Background workers use their own sessions, so the connection may be
        # used from a different thread than the one that created it.
        kwargs["connect_args"] = {"check_same_thread": False}
        if database_url in _IN_MEMORY_URLS:
            kwargs["poolclass"] = StaticPool
    engine = create_engine(database_url, **kwargs)
    if database_url.startswith("sqlite"):
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a factory; each request or worker task opens its own Session."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
