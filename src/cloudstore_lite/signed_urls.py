import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status

from cloudstore_lite.config import Settings


def build_signature(secret: str, object_id: UUID, expires: int) -> str:
    message = f"{object_id}:{expires}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def build_signed_download_url(
    base_url: str,
    object_id: UUID,
    settings: Settings,
    expires_in_seconds: int | None = None,
) -> tuple[str, datetime]:
    ttl_seconds = expires_in_seconds or settings.signed_url_ttl_seconds
    expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
    expires_epoch = int(expires_at.timestamp())
    signature = build_signature(settings.signed_url_secret, object_id, expires_epoch)
    url = f"{base_url.rstrip('/')}/signed/objects/{object_id}?expires={expires_epoch}&signature={signature}"
    return url, expires_at


def validate_signature(
    object_id: UUID,
    expires: int,
    signature: str,
    settings: Settings,
) -> None:
    now_epoch = int(datetime.now(UTC).timestamp())
    if expires < now_epoch:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Signed URL has expired.")

    expected = build_signature(settings.signed_url_secret, object_id, expires)
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Signed URL signature is invalid.")

