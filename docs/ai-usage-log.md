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

### Entry M2-3: Glucose Logging (M1) and Health Trend Analysis (M2) (responsible: Muhammad Abubakar)

| Field | Entry |
|---|---|
| Tool used | Claude (Anthropic), model Claude Opus 5.5 |
| Purpose | Generate modules M1 and M2 following the M1 design: `GlucoseService` with `ReadingRepository`, `SqlReadingRepository`, `TrendService` with the `TrendDetector` Strategy (`PostMealHighDetector`, `TimeOfDayLowDetector`), the glucose and trends API, and their tests. |
| Prompt / activity summary | Asked for M1 and M2 exactly as in the M1 class diagram, RTM v1 (FR-GL-01 to FR-GL-04, FR-TA-01 to FR-TA-04) and the low-coupling rule (M2 reads glucose only through `GlucoseService`), committed test-first. |
| AI-generated material adopted | `backend/app/domain/glucose.py`, `domain/trends.py`, `services/glucose_service.py`, `services/trend_service.py`, `services/trend_detectors.py`, `infrastructure/db/reading_repository.py`, `api/glucose.py`, `api/glucose_schemas.py`, changes to `main.py` and `db/models.py`, and the M1/M2 tests. |
| Modifications made | _[Fill in: anything you changed before adopting it, or "None".]_ |
| Verification performed | Each failing test was run before its implementation and the full suite after it (red-green); boundary tests at 19/20/600/601, 69/70/180/181 and 179/180/181 minutes; Pylint and coverage checked; pull request reviewed by another member. |

### Entry M2-4: CA-06, reports interrupted by a restart (responsible: Muhammad Hamid Quyyum)

| Field | Entry |
|---|---|
| Tool used | Claude (Anthropic), model Claude Opus 5.5, in Claude Code |
| Purpose | Implement corrective action CA-06 from the SE431 report: reports left `pending` or `processing` by a server restart are marked `failed` at start-up, and a file whose earlier report failed can be uploaded again instead of getting 409. |
| Prompt / activity summary | Asked to continue the M2 handoff and implement CA-06 test-first, keeping the M4 thread-safety strategy (all writes under the service's `asyncio.Lock`). |
| AI-generated material adopted | `LabReportRepository.fail_unfinished` and `delete` (domain interface and `SqlLabReportRepository`), `ReportService.recover_interrupted` and the re-upload path in `ReportService.upload`, the start-up call in `main.py` lifespan, and the new tests in `test_report_repository.py`, `test_report_upload.py`, `test_reports_api.py` and `report_fakes.py`. |
| Modifications made | _[Fill in: anything you changed before adopting it, or "None".]_ |
| Verification performed | The new tests were run and seen failing (9 failures) before the implementation; afterwards the full suite passed (240 tests, 100% coverage) and Pylint scored 9.99. |
