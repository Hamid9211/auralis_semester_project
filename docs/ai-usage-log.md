# AI Usage Log

Milestone 1 entries are in the appendices of the M1 reports. Milestone 2 entries follow.

## Milestone 2

### Entry M2-1: Core architecture (responsible: Muhammad Hamid Quyyum)

| Field | Entry |
|---|---|
| Tool used | Claude (Anthropic), model Claude Opus 5.5 |
| Purpose | Generate the core backend architecture: settings, exception hierarchy and central error handlers, SQLAlchemy schema, app factory, health endpoint, CI workflow, and their tests. |
| Prompt / activity summary | Asked for a Day 1 core architecture consistent with the M1 design (layered architecture, M1 exception hierarchy, M1 schema), committed test-first. |
| AI-generated material adopted | `backend/app/core/*`, `backend/app/api/error_handlers.py`, `dependencies.py`, `health.py`, `backend/app/infrastructure/db/*`, `backend/app/main.py`, the tests in `backend/tests/`, `.github/workflows/ci.yml`, `.pylintrc`, README. |
| Modifications made | _[Fill in: anything the team changed before adopting it, or "None".]_ |
| Verification performed | Each failing test was run before its implementation and the full suite after it (red-green), with pytest locally; Pylint score checked against the NFR-07 threshold of 8.0; CI run on GitHub Actions after pushing; pull request reviewed by another member. |
