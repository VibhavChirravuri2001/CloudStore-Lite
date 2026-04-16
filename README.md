# CloudStore-Lite

CloudStore-Lite is a lightweight object storage service built for the kind of backend platform work most cloud infrastructure teams care about: APIs, durable metadata, supportability, and safe file handling.

## Planned capabilities

- Upload, download, list, and delete objects over HTTP
- PostgreSQL-backed metadata
- Dockerized local development
- API key protection for control-plane routes
- Signed URLs for time-limited downloads
- Failure-safe upload finalization with cleanup on error
- Simple test coverage for the storage API

## Tech stack

- FastAPI for the HTTP API
- SQLAlchemy for metadata persistence
- PostgreSQL for deployment metadata storage
- Local filesystem storage backend for object payloads
- Docker and Docker Compose for containerized runs

## Repository roadmap

1. Scaffold the service and persistence layer
2. Implement object lifecycle endpoints
3. Add auth, signed URLs, and health/readiness behavior
4. Add Docker assets and developer docs
5. Add tests and validation

