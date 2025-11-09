# Security

## Authentication & Authorization
- JWT access tokens (15m), refresh tokens (7d)
- Per‑user namespaces (schema or row‑level security) in Postgres

## Secrets
- Never committed. Use environment variables and Fly secrets.
- Optional Vault/1Password for local dev.

## Input Validation
- Pydantic schemas on all request bodies
- Strategy sandbox: restricted imports, no network

## Transport
- TLS via Fly edge; HTTPS enforced

## Audit
- Every API call and job stores actor, timestamp, checksum, and result
- Immutable job payloads (append‑only logs)
