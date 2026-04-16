import hashlib
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile


CHUNK_SIZE = 1024 * 1024


@dataclass(slots=True)
class StoredPayload:
    storage_key: str
    checksum_sha256: str
    size_bytes: int
    content_type: str


def retry_operation(operation, attempts: int = 3, delay_seconds: float = 0.1) -> None:
    last_error: OSError | None = None
    for attempt in range(1, attempts + 1):
        try:
            operation()
            return
        except OSError as exc:
            last_error = exc
            if attempt == attempts:
                raise
            time.sleep(delay_seconds * attempt)
    if last_error is not None:
        raise last_error


class LocalObjectStorage:
    def __init__(self, root: Path):
        self.root = root
        self.objects_dir = root / "objects"
        self.temp_dir = root / "tmp"
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def save_upload(self, upload: UploadFile) -> StoredPayload:
        storage_key = uuid.uuid4().hex
        temp_path = self.temp_dir / f"{storage_key}.part"
        final_path = self.objects_dir / storage_key
        checksum = hashlib.sha256()
        size_bytes = 0

        try:
            with temp_path.open("wb") as handle:
                while True:
                    chunk = upload.file.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    handle.write(chunk)
                    checksum.update(chunk)
                    size_bytes += len(chunk)

            retry_operation(lambda: os.replace(temp_path, final_path))
        except Exception:
            self._safe_unlink(temp_path)
            self._safe_unlink(final_path)
            raise
        finally:
            upload.file.close()

        return StoredPayload(
            storage_key=storage_key,
            checksum_sha256=checksum.hexdigest(),
            size_bytes=size_bytes,
            content_type=upload.content_type or "application/octet-stream",
        )

    def path_for(self, storage_key: str) -> Path:
        return self.objects_dir / storage_key

    def delete(self, storage_key: str) -> None:
        self._safe_unlink(self.path_for(storage_key))

    def _safe_unlink(self, path: Path) -> None:
        if not path.exists():
            return
        retry_operation(path.unlink)
