import logging
import time
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from cloudstore_lite.auth import require_api_key
from cloudstore_lite.config import get_settings
from cloudstore_lite.db import get_db_session, init_db
from cloudstore_lite.models import StoredObject
from cloudstore_lite.schemas import (
    DeleteResponse,
    HealthStatus,
    ObjectMetadata,
    SignedURLRequest,
    SignedURLResponse,
)
from cloudstore_lite.signed_urls import build_signed_download_url, validate_signature
from cloudstore_lite.storage import LocalObjectStorage

logger = logging.getLogger("cloudstore_lite.requests")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.storage = LocalObjectStorage(settings.storage_root)
    init_db()
    yield


app = FastAPI(title="CloudStore-Lite", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    start = time.perf_counter()
    request.state.request_id = request_id

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "request_failed request_id=%s method=%s path=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            duration_ms,
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
    logger.info(
        "request_completed request_id=%s method=%s path=%s status_code=%s duration_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


def get_storage() -> LocalObjectStorage:
    return app.state.storage


def to_metadata(record: StoredObject) -> ObjectMetadata:
    return ObjectMetadata.model_validate(record, from_attributes=True)


@app.get("/health/live", response_model=HealthStatus, tags=["health"])
def liveness() -> HealthStatus:
    return HealthStatus(status="ok")


@app.get("/health/ready", response_model=HealthStatus, tags=["health"])
def readiness(session: Session = Depends(get_db_session)) -> HealthStatus:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not ready.",
        ) from exc
    return HealthStatus(status="ok")


@app.post("/objects", response_model=ObjectMetadata, status_code=status.HTTP_201_CREATED, tags=["objects"])
def upload_object(
    file: UploadFile = File(...),
    _: str = Depends(require_api_key),
    session: Session = Depends(get_db_session),
    storage: LocalObjectStorage = Depends(get_storage),
) -> ObjectMetadata:
    payload = storage.save_upload(file)
    record = StoredObject(
        filename=file.filename or "unnamed",
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        checksum_sha256=payload.checksum_sha256,
        storage_key=payload.storage_key,
    )

    try:
        session.add(record)
        session.commit()
        session.refresh(record)
    except SQLAlchemyError as exc:
        session.rollback()
        storage.delete(payload.storage_key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload metadata could not be persisted.",
        ) from exc

    return to_metadata(record)


@app.get("/objects", response_model=list[ObjectMetadata], tags=["objects"])
def list_objects(
    _: str = Depends(require_api_key),
    session: Session = Depends(get_db_session),
) -> list[ObjectMetadata]:
    records = session.scalars(select(StoredObject).order_by(StoredObject.created_at.desc())).all()
    return [to_metadata(record) for record in records]


@app.get("/objects/{object_id}", tags=["objects"])
def download_object(
    object_id: UUID,
    _: str = Depends(require_api_key),
    session: Session = Depends(get_db_session),
    storage: LocalObjectStorage = Depends(get_storage),
):
    record = session.get(StoredObject, object_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Object not found.")

    path = storage.path_for(record.storage_key)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Object payload is missing from storage.",
        )

    return FileResponse(path=path, media_type=record.content_type, filename=record.filename)


@app.post("/objects/{object_id}/signed-url", response_model=SignedURLResponse, tags=["objects"])
def create_signed_url(
    object_id: UUID,
    request: Request,
    payload: SignedURLRequest,
    _: str = Depends(require_api_key),
    session: Session = Depends(get_db_session),
) -> SignedURLResponse:
    record = session.get(StoredObject, object_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Object not found.")

    url, expires_at = build_signed_download_url(
        str(request.base_url),
        record.id,
        get_settings(),
        payload.expires_in_seconds,
    )
    return SignedURLResponse(url=url, expires_at=expires_at)


@app.get("/signed/objects/{object_id}", tags=["objects"])
def download_object_via_signed_url(
    object_id: UUID,
    expires: int,
    signature: str,
    session: Session = Depends(get_db_session),
    storage: LocalObjectStorage = Depends(get_storage),
):
    validate_signature(object_id, expires, signature, get_settings())
    record = session.get(StoredObject, object_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Object not found.")

    path = storage.path_for(record.storage_key)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Object payload is missing from storage.",
        )

    return FileResponse(path=path, media_type=record.content_type, filename=record.filename)


@app.delete("/objects/{object_id}", response_model=DeleteResponse, tags=["objects"])
def delete_object(
    object_id: UUID,
    _: str = Depends(require_api_key),
    session: Session = Depends(get_db_session),
    storage: LocalObjectStorage = Depends(get_storage),
) -> DeleteResponse:
    record = session.get(StoredObject, object_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Object not found.")

    storage_key = record.storage_key
    try:
        session.delete(record)
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Object metadata could not be deleted.",
        ) from exc

    storage.delete(storage_key)
    return DeleteResponse(status="deleted")
