from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from cloudstore_lite import db as db_module
from cloudstore_lite.config import get_settings
from cloudstore_lite.db import Base, get_db_session
from cloudstore_lite.main import app
from cloudstore_lite.storage import LocalObjectStorage


@pytest.fixture
def client(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "test.db"
    storage_root = tmp_path / "storage"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    monkeypatch.setenv("CLOUDSTORE_DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("CLOUDSTORE_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("CLOUDSTORE_API_KEY", "test-api-key")
    monkeypatch.setenv("CLOUDSTORE_SIGNED_URL_SECRET", "test-signed-url-secret")
    get_settings.cache_clear()

    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(db_module, "SessionLocal", testing_session)

    def override_db_session():
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_db_session
    app.state.storage = LocalObjectStorage(storage_root)
    monkeypatch.setattr("cloudstore_lite.main.init_db", lambda: None)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    engine.dispose()
    get_settings.cache_clear()


def test_object_lifecycle_flow(client: TestClient) -> None:
    upload_response = client.post(
        "/objects",
        headers={"X-API-Key": "test-api-key"},
        files={"file": ("hello.txt", b"hello cloudstore", "text/plain")},
    )
    assert upload_response.status_code == 201
    metadata = upload_response.json()

    list_response = client.get("/objects", headers={"X-API-Key": "test-api-key"})
    assert list_response.status_code == 200
    listed_objects = list_response.json()
    assert len(listed_objects) == 1
    assert listed_objects[0]["filename"] == "hello.txt"

    download_response = client.get(f"/objects/{metadata['id']}", headers={"X-API-Key": "test-api-key"})
    assert download_response.status_code == 200
    assert download_response.content == b"hello cloudstore"

    delete_response = client.delete(f"/objects/{metadata['id']}", headers={"X-API-Key": "test-api-key"})
    assert delete_response.status_code == 200
    assert delete_response.json() == {"status": "deleted"}


def test_signed_download_url_flow(client: TestClient) -> None:
    upload_response = client.post(
        "/objects",
        headers={"X-API-Key": "test-api-key"},
        files={"file": ("report.txt", b"signed download", "text/plain")},
    )
    object_id = upload_response.json()["id"]

    signed_url_response = client.post(
        f"/objects/{object_id}/signed-url",
        headers={"X-API-Key": "test-api-key"},
        json={"expires_in_seconds": 300},
    )
    assert signed_url_response.status_code == 200
    signed_url = signed_url_response.json()["url"]

    download_response = client.get(signed_url)
    assert download_response.status_code == 200
    assert download_response.content == b"signed download"


def test_protected_routes_require_api_key(client: TestClient) -> None:
    response = client.get("/objects")
    assert response.status_code == 401


def test_failed_metadata_commit_removes_uploaded_payload(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "cleanup.db"
    storage_root = tmp_path / "storage"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    monkeypatch.setenv("CLOUDSTORE_DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("CLOUDSTORE_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("CLOUDSTORE_API_KEY", "test-api-key")
    monkeypatch.setenv("CLOUDSTORE_SIGNED_URL_SECRET", "test-signed-url-secret")
    get_settings.cache_clear()

    Base.metadata.create_all(bind=engine)
    app.state.storage = LocalObjectStorage(storage_root)
    monkeypatch.setattr("cloudstore_lite.main.init_db", lambda: None)

    def failing_db_session():
        session = testing_session()
        original_commit = session.commit

        def fail_commit():
            session.commit = original_commit
            raise SQLAlchemyError("forced commit failure")

        session.commit = fail_commit
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = failing_db_session

    with TestClient(app) as test_client:
        response = test_client.post(
            "/objects",
            headers={"X-API-Key": "test-api-key"},
            files={"file": ("broken.txt", b"cleanup me", "text/plain")},
        )

    assert response.status_code == 500
    assert not any((storage_root / "objects").glob("*"))

    app.dependency_overrides.clear()
    engine.dispose()
    get_settings.cache_clear()
