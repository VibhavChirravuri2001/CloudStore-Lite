# CloudStore-Lite

CloudStore-Lite is a lightweight object storage service built to mirror the kind of backend platform work common in cloud infrastructure teams: file lifecycle APIs, durable metadata, safe upload finalization, container-first operations, and straightforward supportability.

## What it does

- Upload, download, list, and delete objects over HTTP
- Persist object metadata in PostgreSQL
- Store object payloads on disk with atomic temp-file finalization
- Protect control-plane routes with an API key
- Generate signed download URLs with expiration
- Expose liveness and readiness endpoints for operations

## Architecture

- FastAPI serves the HTTP API
- SQLAlchemy manages metadata persistence
- PostgreSQL stores object metadata
- Local filesystem storage holds object payloads
- Docker Compose boots the API and database together

The upload path is intentionally failure-safe: files are streamed into a temporary location, hashed while writing, then atomically moved into place. If metadata persistence fails after the file is written, the service deletes the stored payload so the system does not accumulate partial state.

## API summary

Protected with `X-API-Key`:

- `POST /objects` uploads a multipart file
- `GET /objects` lists stored object metadata
- `GET /objects/{object_id}` downloads an object directly
- `DELETE /objects/{object_id}` deletes an object
- `POST /objects/{object_id}/signed-url` creates a time-limited download URL

Public:

- `GET /signed/objects/{object_id}` downloads with a valid signature
- `GET /health/live` liveness probe
- `GET /health/ready` readiness probe with database validation

## Environment

Copy `.env.example` to `.env` and adjust values as needed:

- `CLOUDSTORE_DATABASE_URL`: SQLAlchemy connection string
- `CLOUDSTORE_STORAGE_ROOT`: directory for persisted object payloads
- `CLOUDSTORE_API_KEY`: required for protected routes
- `CLOUDSTORE_SIGNED_URL_SECRET`: HMAC secret used for signed URLs
- `CLOUDSTORE_SIGNED_URL_TTL_SECONDS`: default signed URL lifetime

## Run locally with Docker

```bash
cp .env.example .env
docker compose up --build
```

The API will be available at `http://localhost:8000`.

## Example workflow

Upload a file:

```bash
curl -X POST "http://localhost:8000/objects" \
  -H "X-API-Key: dev-api-key" \
  -F "file=@README.md"
```

List objects:

```bash
curl "http://localhost:8000/objects" \
  -H "X-API-Key: dev-api-key"
```

Create a signed URL:

```bash
curl -X POST "http://localhost:8000/objects/<object-id>/signed-url" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key" \
  -d "{\"expires_in_seconds\": 300}"
```

## Next step

The remaining work is test coverage so the upload, delete, and signed-download flows are easy to validate and evolve.
