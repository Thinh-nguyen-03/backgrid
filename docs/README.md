# Documentation Guide

Core documentation for Backgrid trading backtester.

---

## Getting Started

1. **[../README.md](../README.md)** - Project overview and quick start
2. **[SETUP.md](SETUP.md)** - Complete setup and deployment guide
3. **[API.md](API.md)** - API endpoints and usage examples

---

## Core Documentation

**Architecture & Design**
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design, component breakdown, decision rationale
- **[DATA_MODEL.md](DATA_MODEL.md)** - Database schema and relationships
- **[DECISION_LOG.md](DECISION_LOG.md)** - Technical decisions with rationale (Phases 1–3)

**Development**
- **[SETUP.md](SETUP.md)** - Development environment and deployment
- **[CODING_STANDARDS.md](CODING_STANDARDS.md)** - Code style and conventions
- **[STRATEGY_SDK.md](STRATEGY_SDK.md)** - Building custom trading strategies

**Planning**
- **[ENGINEERING_REVIEW.md](ENGINEERING_REVIEW.md)** - Phase 3 improvement plan (11 items, prioritized)

**Reference**
- **[GLOSSARY.md](GLOSSARY.md)** - Terms and definitions
- **[LEARNING_GUIDE.md](LEARNING_GUIDE.md)** - Key formulas and concepts
- **[API.md](API.md)** - API specification

---

## Archive

Historical documents preserved for reference:

**[archive/phase2/](archive/phase2/)**
- Phase 2 handoff documents, implementation plans, task lists

**[archive/](archive/)**
- Original specification documents, early design docs, completed feature plans
- Includes: Strategy Import design/summary, parallel implementation plan

---

## Document Index

| Document | Purpose | Audience |
|----------|---------|----------|
| [SETUP.md](SETUP.md) | Setup, deployment, configuration | Developers, DevOps |
| [API.md](API.md) | API endpoints and usage | Developers, API consumers |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design and decision rationale | Developers, Architects |
| [DATA_MODEL.md](DATA_MODEL.md) | Database schema | Developers |
| [DECISION_LOG.md](DECISION_LOG.md) | Technical decisions | All contributors |
| [ENGINEERING_REVIEW.md](ENGINEERING_REVIEW.md) | Phase 3 improvement plan | Developers |
| [CODING_STANDARDS.md](CODING_STANDARDS.md) | Code style guide | Developers |
| [STRATEGY_SDK.md](STRATEGY_SDK.md) | Custom strategy development | Strategy developers |
| [GLOSSARY.md](GLOSSARY.md) | Terms and definitions | All users |
| [LEARNING_GUIDE.md](LEARNING_GUIDE.md) | Quick reference formulas | Developers, Quants |

---

## Quick Links

- **Interactive API Docs**: http://localhost:8000/docs (when server running)
- **GitHub Repository**: https://github.com/Thinh-nguyen-03/backgrid
- **Test Coverage**: Run `pytest tests/ --cov=src --cov-report=html`
