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
| Modifications made | AI helped with this task in general; the responsible member reviewed the output before adopting it. |
| Verification performed | Each failing test was run before its implementation and the full suite after it (red-green), with pytest locally; Pylint score checked against the NFR-07 threshold of 8.0; CI run on GitHub Actions after pushing; pull request reviewed by another member. |

### Entry M2-2: Medical Report Analyzer, module M4 (responsible: Muhammad Hamid Quyyum)

| Field | Entry |
|---|---|
| Tool used | Claude (Anthropic), model Claude Opus 5.5 |
| Purpose | Generate module M4 following the M1 design: domain model and interfaces, lab value parser, Factory Method (`ExplanationGeneratorFactory`), Adapters (`GroqExplanationAdapter`, `PyMuPDFTextExtractor`), template fallback, SQL repository, `ReportService` with the async queue and lock, `ReportWorker`, the reports API, their tests, and the thread-safety document. |
| Prompt / activity summary | Asked for M4 exactly as specified in the M1 class diagram, pattern table and thread-safety strategy, committed test-first. |
| AI-generated material adopted | `backend/app/domain/lab_reports.py`, `services/lab_value_parser.py`, `services/report_service.py`, `infrastructure/groq_adapter.py`, `pymupdf_extractor.py`, `template_explanation.py`, `explanation_factory.py`, `db/report_repository.py`, `api/reports.py`, `api/report_schemas.py`, changes to `main.py`, `core/exceptions.py` and `api/error_handlers.py`, the M4 tests and fixtures, `docs/m2/thread-safety.md`. |
| Modifications made | AI helped with this task in general; the responsible member reviewed the output before adopting it. |
| Verification performed | Each failing test was run before its implementation and the full suite after it (red-green); concurrency tests run 100 simultaneous uploads; Pylint and coverage checked locally and in CI; pull request reviewed by another member. |

### Entry M2-3: Glucose Logging (M1) and Health Trend Analysis (M2) (responsible: Muhammad Abubakar)

| Field | Entry |
|---|---|
| Tool used | Claude (Anthropic), model Claude Opus 5.5 |
| Purpose | Generate modules M1 and M2 following the M1 design: `GlucoseService` with `ReadingRepository`, `SqlReadingRepository`, `TrendService` with the `TrendDetector` Strategy (`PostMealHighDetector`, `TimeOfDayLowDetector`), the glucose and trends API, and their tests. |
| Prompt / activity summary | Asked for M1 and M2 exactly as in the M1 class diagram, RTM v1 (FR-GL-01 to FR-GL-04, FR-TA-01 to FR-TA-04) and the low-coupling rule (M2 reads glucose only through `GlucoseService`), committed test-first. |
| AI-generated material adopted | `backend/app/domain/glucose.py`, `domain/trends.py`, `services/glucose_service.py`, `services/trend_service.py`, `services/trend_detectors.py`, `infrastructure/db/reading_repository.py`, `api/glucose.py`, `api/glucose_schemas.py`, changes to `main.py` and `db/models.py`, and the M1/M2 tests. |
| Modifications made | AI helped with this task in general; the responsible member reviewed the output before adopting it. |
| Verification performed | Each failing test was run before its implementation and the full suite after it (red-green); boundary tests at 19/20/600/601, 69/70/180/181 and 179/180/181 minutes; Pylint and coverage checked; pull request reviewed by another member. |

### Entry M2-4: CA-06, reports interrupted by a restart (responsible: Muhammad Hamid Quyyum)

| Field | Entry |
|---|---|
| Tool used | Claude (Anthropic), model Claude Opus 5.5, in Claude Code |
| Purpose | Implement corrective action CA-06 from the SE431 report: reports left `pending` or `processing` by a server restart are marked `failed` at start-up, and a file whose earlier report failed can be uploaded again instead of getting 409. |
| Prompt / activity summary | Asked to continue the M2 handoff and implement CA-06 test-first, keeping the M4 thread-safety strategy (all writes under the service's `asyncio.Lock`). |
| AI-generated material adopted | `LabReportRepository.fail_unfinished` and `delete` (domain interface and `SqlLabReportRepository`), `ReportService.recover_interrupted` and the re-upload path in `ReportService.upload`, the start-up call in `main.py` lifespan, and the new tests in `test_report_repository.py`, `test_report_upload.py`, `test_reports_api.py` and `report_fakes.py`. |
| Modifications made | AI helped with this task in general; the responsible member reviewed the output before adopting it. |
| Verification performed | The new tests were run and seen failing (9 failures) before the implementation; afterwards the full suite passed (240 tests, 100% coverage) and Pylint scored 9.99. |

### Entry M2-5: Meal and Nutrition Logging, module M3 (responsible: Ahmad Uzair Shah)

| Field | Entry |
|---|---|
| Tool used | Claude (Anthropic), model Claude Opus 5.5 |
| Purpose | Generate module M3 following the M1 design: meal domain model, `FoodRepository` and `MealRepository` (separate interfaces), `MealService` (search, log, daily totals, meal-glucose linking through `GlucoseService`), SQL repositories, the nutrition table seed, the meals API, and their tests. |
| Prompt / activity summary | Asked for M3 exactly as in the M1 class diagram and RTM v1 (FR-ML-01 to FR-ML-05), committed test-first. |
| AI-generated material adopted | `backend/app/domain/meals.py`, `services/meal_service.py`, `infrastructure/db/meal_repository.py`, `infrastructure/db/nutrition_seed.py`, `api/meals.py`, `api/meal_schemas.py`, changes to `main.py`, `db/models.py`, `db/init_db.py` and `core/exceptions.py`, and the M3 tests. |
| Modifications made | AI helped with this task in general; the responsible member reviewed the output before adopting it. |
| Verification performed | Each failing test was run before its implementation and the full suite after it (red-green); boundary tests on portion (0.4/0.5/3.0/3.1) and the link window (119/120/121 min); nutrition values checked against USDA FoodData Central; Pylint and coverage checked; pull request reviewed by another member. |

### Entry M2-6: Static analysis fixes CA-02 to CA-04 (responsible: Ahmad Uzair Shah)

| Field | Entry |
|---|---|
| Tool used | Claude (Anthropic) |
| Purpose | Prepare the fixes for the Pylint findings of the M2 static analysis run and the static analysis report. |
| Prompt / activity summary | Asked for minimal, test-preserving fixes for W0621 and R1710 in the test suite, a test-specific Pylint configuration with a CI step, and a report of the runs and triage (SA-1 to SA-6, F-01 to F-07). |
| AI-generated material adopted | Renamed test helper (CA-02), explicit failure in `_wait_until_finished` (CA-03), `backend/tests/.pylintrc` and the CI lint step (CA-04), `docs/m2/static-analysis.md`. Commits 93f805f, b646701, 3214576, 32dff33; PR #18. |
| Modifications made | AI helped with this task in general; the responsible member reviewed the output before adopting it. |
| Verification performed | All 318 tests passed after each commit; Pylint app 9.98 (only R0801, deferred as CA-08) and tests 10.00; CI green on PR #18; reviewed by another member. |

### Entry M2-7: Fagan inspection INS-01 record and rework CA-11 to CA-17 (responsible: Muhammad Hamid Quyyum)

| Field | Entry |
|---|---|
| Tool used | Claude (Anthropic) |
| Purpose | LaTeX template for the INS-01 inspection record (plan, checklist C1–C12, preparation logs, defect log, CAPA table, automatic metrics), a list of candidate issues in report_service.py for preparation, wording help, and the test-first rework of the accepted defects. |
| Prompt / activity summary | Asked for an editable inspection record with real project data (version, line ranges, tests, CA numbering), candidate issues with line numbers, and test-then-fix commits for each accepted defect. |
| AI-generated material adopted | Inspection record template; rework commits on fix/ins-01-defects: CA-11 82cbb36/7a82b5a, CA-12 d4b2630/fe752bf, CA-14 911a2de/92eaee9, CA-15 2ce03ff/2f35db1, CA-16 fda5b70/e26718c, CA-17 9fb5398; PR #19, merge 668f137. |
| Not AI-generated | The inspection itself: times, preparation minutes, the issues raised, who raised them, dispositions, the decision and the signatures come from the team and the external inspector. |
| Modifications made | AI helped with this task in general; the responsible member reviewed the output before adopting it. |
| Verification performed | Each failing test was run before its fix; after merge 328 tests pass, 100% statement coverage (1287 statements), Pylint app 9.98 and tests 10.00; PR #19 reviewed by the moderator. |
