# Coding Standards

## Python
- black, isort, flake8, mypy (strict optional)
- Dataclasses/TypedDict for DTOs; type hints everywhere
- No global state; dependency injection via function args

## Go
- golangci‑lint, go vet
- Context propagation; avoid blocking I/O in hot paths
- Prefer channels over shared mutexes; immutable inputs

## General
- Structured logs only; no print debugging
- Functions ≤ ~40 lines where feasible
- PRs require tests + docs updates; CI must be green
