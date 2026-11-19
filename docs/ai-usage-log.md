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

### Entry M2-2: Medical Report Analyzer, module M4 (responsible: Muhammad Hamid Quyyum)

| Field | Entry |
|---|---|
| Tool used | Claude (Anthropic), model Claude Opus 5.5 |
| Purpose | Generate module M4 following the M1 design: domain model and interfaces, lab value parser, Factory Method (`ExplanationGeneratorFactory`), Adapters (`GroqExplanationAdapter`, `PyMuPDFTextExtractor`), template fallback, SQL repository, `ReportService` with the async queue and lock, `ReportWorker`, the reports API, their tests, and the thread-safety document. |
| Prompt / activity summary | Asked for M4 exactly as specified in the M1 class diagram, pattern table and thread-safety strategy, committed test-first. |
| AI-generated material adopted | `backend/app/domain/lab_reports.py`, `services/lab_value_parser.py`, `services/report_service.py`, `infrastructure/groq_adapter.py`, `pymupdf_extractor.py`, `template_explanation.py`, `explanation_factory.py`, `db/report_repository.py`, `api/reports.py`, `api/report_schemas.py`, changes to `main.py`, `core/exceptions.py` and `api/error_handlers.py`, the M4 tests and fixtures, `docs/m2/thread-safety.md`. |
| Modifications made | _[Fill in: anything the team changed before adopting it, or "None".]_ |
| Verification performed | Each failing test was run before its implementation and the full suite after it (red-green); concurrency tests run 100 simultaneous uploads; Pylint and coverage checked locally and in CI; pull request reviewed by another member. |
