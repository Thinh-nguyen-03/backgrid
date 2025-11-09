# Decision Log

## Template
Every major technology addition must use this template:

```markdown
## Decision: [Technology] (Date: YYYY-MM-DD)

### Problem
[What you measured - be specific]

### Evidence
```bash
# Include profiler output, benchmark, or error log
```

### Alternatives Considered
- **Alternative 1**: Pros/cons
- **Alternative 2**: Pros/cons

### Decision
Why you chose this technology

### Impact
Before/after metrics

### Tradeoffs
What you gave up to get this benefit
```

---

## Entries

### Pending Decisions

#### Celery + Redis
- **Trigger**: Measured job latency >5s
- **Status**: Not yet implemented
- **Estimated**: Phase 2

#### Go gRPC Metrics Service
- **Trigger**: Profiler shows metrics >50% runtime
- **Status**: Not yet implemented
- **Estimated**: Phase 3

#### TimescaleDB
- **Trigger**: PostgreSQL queries slow on 25M+ rows
- **Status**: Not yet implemented
- **Estimated**: Phase 3

#### JWT Auth
- **Trigger**: Multiple users need isolation
- **Status**: Not yet implemented
- **Estimated**: Phase 3
