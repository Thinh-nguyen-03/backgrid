# Coding Standards

**Phase 2 Complete** - 650 tests passing, >95% coverage

## Python

### Code Quality
- Type hints for all function signatures
- Dataclasses/TypedDict for DTOs
- No global state; dependency injection via function args
- Functions ≤ ~40 lines where feasible

### Tooling (Optional)
- black, isort, flake8, mypy (not enforced in Phase 2)
- pytest for all tests
- SQLAlchemy 2.0 syntax

### Comments and Documentation
- **Minimal, concise, professional** comments/docstrings
- Only add when needed, not for every step
- **No** `======` or `-------` dividers in comments/logs
- **No** emojis or icons in codebase
- Docstrings for public APIs and complex logic only

### Testing
- All new features require tests
- Test files follow `test_*.py` pattern
- Use fixtures for common setup
- Mock external dependencies (YahooDataLoader, PostgreSQL)
- Aim for >95% coverage

## Go (Phase 3)
- golangci‑lint, go vet
- Context propagation; avoid blocking I/O in hot paths
- Prefer channels over shared mutexes; immutable inputs

## General
- Structured logs only; no print debugging
- PRs require tests + docs updates
- All tests must pass before merge
