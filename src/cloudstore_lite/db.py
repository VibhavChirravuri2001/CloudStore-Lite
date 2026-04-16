from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from cloudstore_lite.config import get_settings


class Base(DeclarativeBase):
    """Base class for ORM models."""


settings = get_settings()
engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    from cloudstore_lite import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

