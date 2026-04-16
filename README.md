# CloudStore-Lite

CloudStore-Lite is a lightweight object storage service designed to showcase backend engineering work that maps closely to cloud-platform roles: API design, object lifecycle management, durable metadata, operational health checks, secure access patterns, and containerized local development.

## Why this project matters

This project is intentionally aligned with the kind of work common in infrastructure and platform teams:

- Storage-oriented API design
- PostgreSQL-backed metadata persistence
- Safe handling of partial failures during upload
- Docker-first developer workflow
- Simple operational health endpoints
- Authentication and signed access flows
- Testable behavior with clear expected outcomes

## Features

- Upload files over HTTP using multipart form data
- Download files directly through an authenticated endpoint
- List uploaded objects and their metadata
- Delete objects and their stored payloads
- Persist metadata in PostgreSQL
- Store file payloads on local disk
- Stream uploads into temporary files and atomically finalize them
- Remove stored payloads if metadata persistence fails
- Protect control-plane endpoints with an API key
- Generate time-limited signed download URLs
- Expose liveness and readiness endpoints

## Architecture

- FastAPI powers the HTTP API
- SQLAlchemy manages persistence
- PostgreSQL stores metadata
- Local filesystem storage holds object payloads
- Docker Compose runs the API and database together

```mermaid
flowchart LR
    Client["Client / cURL / TestClient"] --> API["FastAPI API Layer"]
    API --> Auth["API Key + Signed URL Validation"]
    API --> Meta["SQLAlchemy + PostgreSQL Metadata"]
    API --> Storage["Local Filesystem Object Storage"]
    Storage --> Disk["Atomic Final Object File"]
    Storage --> Temp["Temporary .part Upload File"]
```

## Reliability guarantees

CloudStore-Lite currently aims to preserve a few simple but important invariants:

- An object is not listed unless its metadata commit succeeds
- A file is not exposed as a final object until it has been fully written to disk
- If metadata persistence fails after upload, the finalized payload is deleted
- Signed download routes reject expired or tampered signatures
- Protected routes reject missing or invalid API keys
- Readiness only reports success when the service can talk to the database

## Operations and debugging signals

The service includes lightweight request correlation and timing information:

- Every response includes `X-Request-ID`
- If the client sends `X-Request-ID`, the service echoes it back
- Every response includes `X-Process-Time-Ms`
- The API logs one structured line per completed request with request ID, method, path, status code, and latency

Example response headers:

```text
X-Request-ID: 0f2c2a87-0a8e-4b1e-8c8f-f4f2c2c3e411
X-Process-Time-Ms: 3.42
```

## Repository structure

```text
src/cloudstore_lite/
  auth.py          API key validation
  config.py        Environment-based settings
  db.py            Database engine and session management
  main.py          FastAPI app and routes
  models.py        SQLAlchemy metadata model
  schemas.py       Request and response models
  signed_urls.py   Signed URL creation and validation
  storage.py       Local object storage and safe upload finalization

tests/
  test_api.py      End-to-end API tests
```

## API overview

Protected with `X-API-Key`:

- `POST /objects`
- `GET /objects`
- `GET /objects/{object_id}`
- `DELETE /objects/{object_id}`
- `POST /objects/{object_id}/signed-url`

Public:

- `GET /signed/objects/{object_id}`
- `GET /health/live`
- `GET /health/ready`

## Environment variables

Copy `.env.example` to `.env` and update values if needed.

- `CLOUDSTORE_DATABASE_URL`
  SQLAlchemy database URL
- `CLOUDSTORE_STORAGE_ROOT`
  Directory used for stored object payloads
- `CLOUDSTORE_API_KEY`
  Required header value for protected routes
- `CLOUDSTORE_SIGNED_URL_SECRET`
  Secret used to generate and validate signed download URLs
- `CLOUDSTORE_SIGNED_URL_TTL_SECONDS`
  Default signed URL expiration time in seconds

Default development values are already provided in `.env.example`.

## Prerequisites

To recreate and run this project locally, you need:

- Python 3.11 or newer
- Docker Desktop or Docker Engine with Compose support
- Git

Optional for local non-Docker runs:

- A running PostgreSQL instance

## How to recreate the project locally

### 1. Clone the repository

```bash
git clone https://github.com/VibhavChirravuri2001/CloudStore-Lite.git
cd CloudStore-Lite
```

Expected result:

- The repository is available locally with `src/`, `tests/`, `Dockerfile`, `docker-compose.yml`, and `.env.example`.

### 2. Create the environment file

macOS/Linux:

```bash
cp .env.example .env
```

PowerShell:

```powershell
Copy-Item .env.example .env
```

Expected result:

- A local `.env` file exists in the repository root.
- The default API key is `dev-api-key`.

### 3. Start the system with Docker

```bash
docker compose up --build
```

Expected result:

- Docker builds the API image.
- PostgreSQL starts successfully.
- The API becomes available at `http://localhost:8000`.
- The readiness endpoint eventually returns HTTP `200`.
- Responses include request-correlation headers such as `X-Request-ID`.

You can verify that with:

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

Expected result:

```json
{"status":"ok"}
```

for both endpoints once the database is ready.

## How to run locally without Docker

This is useful if someone reviewing the project wants to inspect or debug the service directly.

### 1. Install dependencies

```bash
python -m pip install -e .[dev]
```

Expected result:

- The package installs in editable mode.
- Development dependencies including `pytest` and `httpx` are available.

### 2. Configure PostgreSQL

Update `.env` so that `CLOUDSTORE_DATABASE_URL` points to a reachable PostgreSQL database.

Example:

```env
CLOUDSTORE_DATABASE_URL=postgresql+psycopg://cloudstore:cloudstore@localhost:5432/cloudstore
```

Expected result:

- The service can connect to PostgreSQL at startup.

### 3. Run the API

```bash
uvicorn cloudstore_lite.main:app --reload
```

Expected result:

- The FastAPI app starts successfully.
- The service creates the `stored_objects` table if it does not already exist.
- The storage directory is created automatically.
- Request logs include method, path, status, request ID, and latency.

## How to test the service manually

### 1. Upload a file

```bash
curl -X POST "http://localhost:8000/objects" \
  -H "X-API-Key: dev-api-key" \
  -F "file=@README.md"
```

Expected result:

- HTTP status `201 Created`
- Response headers include `X-Request-ID` and `X-Process-Time-Ms`
- JSON response containing:
  - `id`
  - `filename`
  - `content_type`
  - `size_bytes`
  - `checksum_sha256`
  - `created_at`

Example shape:

```json
{
  "id": "8f5f0f7e-5d11-4a37-a7a6-e0d8c5a4cbe1",
  "filename": "README.md",
  "content_type": "application/octet-stream",
  "size_bytes": 1234,
  "checksum_sha256": "...",
  "created_at": "2026-04-15T00:00:00Z"
}
```

### 2. List stored objects

```bash
curl "http://localhost:8000/objects" \
  -H "X-API-Key: dev-api-key"
```

Expected result:

- HTTP status `200 OK`
- A JSON array containing the uploaded object metadata

### 3. Download the file directly

```bash
curl "http://localhost:8000/objects/<object-id>" \
  -H "X-API-Key: dev-api-key" \
  --output downloaded-file
```

Expected result:

- HTTP status `200 OK`
- The downloaded file contents match the original uploaded file

### 4. Create a signed URL

```bash
curl -X POST "http://localhost:8000/objects/<object-id>/signed-url" \
  -H "X-API-Key: dev-api-key" \
  -H "Content-Type: application/json" \
  -d "{\"expires_in_seconds\":300}"
```

Expected result:

- HTTP status `200 OK`
- JSON response with:
  - `url`
  - `expires_at`

Example shape:

```json
{
  "url": "http://localhost:8000/signed/objects/<object-id>?expires=...&signature=...",
  "expires_at": "2026-04-15T00:00:00Z"
}
```

### 5. Download using the signed URL

```bash
curl "<signed-url-from-previous-step>" --output signed-download
```

Expected result:

- HTTP status `200 OK`
- The file downloads without sending `X-API-Key`

### 6. Delete the object

```bash
curl -X DELETE "http://localhost:8000/objects/<object-id>" \
  -H "X-API-Key: dev-api-key"
```

Expected result:

```json
{"status":"deleted"}
```

- The object metadata is removed from PostgreSQL
- The stored file payload is removed from disk

## How to run automated tests

Install dependencies first:

```bash
python -m pip install -e .[dev]
```

Then run:

```bash
python -m pytest --basetemp .pytest_tmp
```

Expected result:

- All tests pass
- Current expected outcome:

```text
6 passed
```

## What the automated tests cover

- Successful upload, list, download, and delete flow
- Signed URL generation and signed download flow
- API key enforcement on protected routes
- Invalid signed URL rejection
- Request ID propagation and latency headers
- Cleanup behavior when metadata commit fails after file upload

## Failure-safe behavior

One of the strongest parts of this project is its handling of partial failures during upload.

Behavior:

- The uploaded file is written to a temporary `.part` file first
- The service computes SHA-256 while streaming the upload
- The file is atomically moved into final storage only after the write completes
- If database persistence fails, the stored payload is deleted
- File move and delete operations are retried to reduce transient filesystem issues

Expected result:

- The service avoids leaving orphaned payloads behind when metadata storage fails

## Failure modes and current behavior

These are the failure cases most relevant to correctness and supportability:

- Missing or invalid API key
  Expected behavior: protected routes return `401`
- Invalid or tampered signed URL
  Expected behavior: signed download route returns `403`
- Expired signed URL
  Expected behavior: signed download route returns `403`
- Database failure during readiness check
  Expected behavior: `/health/ready` returns `503`
- Database failure after file upload but before metadata commit
  Expected behavior: the request returns `500` and the stored payload is deleted
- Interrupted upload before finalization
  Expected behavior: no metadata record is created and no final object is exposed
  Note: temporary `.part` files may remain after abrupt process termination and are a reasonable future cleanup enhancement

## Recruiter and reviewer talking points

This project is a strong fit for cloud/backend roles because it demonstrates:

- Storage API design
- Database-backed metadata
- Secure access control patterns
- Signed URL workflows
- Containerized service delivery
- Operational readiness thinking
- Failure handling and cleanup
- Basic automated verification

## Current status

Implemented:

- Core object lifecycle API
- PostgreSQL metadata storage
- Local object payload storage
- API key authentication
- Signed download URLs
- Dockerized local deployment
- Automated API tests

Not implemented yet:

- S3 or cloud blob backend
- Background jobs
- Multi-node deployment
- Kubernetes manifests
- Rate limiting
- Observability stack integration

## Quick success checklist

Someone reviewing this repository should be able to:

1. Clone the repo
2. Copy `.env.example` to `.env`
3. Run `docker compose up --build`
4. Hit `/health/live` and `/health/ready`
5. Upload a file
6. List and download it
7. Generate and use a signed URL
8. Run `python -m pytest --basetemp .pytest_tmp`

Expected final outcome:

- The service works end to end locally
- All six tests pass
- The repository clearly demonstrates backend, storage, database, Docker, and supportability skills
