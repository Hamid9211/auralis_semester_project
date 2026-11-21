# Static analysis report (Milestone 2)

Tool: **Pylint 4.1.4** (astroid 4.3.4), Python 3.13, run on Windows and in GitHub Actions.
Configuration: `backend/.pylintrc` for `app/`, `backend/tests/.pylintrc` for `tests/`.
Quality gate (NFR-07): score ≥ 8.0/10, enforced by CI on every push.

## Runs

| Run | Code analysed | Command | Score | Findings |
|---|---|---|---|---|
| SA-1 | Core architecture (`feature/core-architecture`, commit `0b80c6e`) | `pylint app` | 3.97/10 | 28 × E1136 unsubscriptable-object |
| SA-2 | Same, after CA-01 (commit `358915b`) | `pylint app` | 10.00/10 | 0 |
| SA-3 | Core + M4 (`feature/report-analyzer`, commit `8d510ed`) | `pylint app` | 10.00/10 | 0 |
| SA-4 | Same, all optional checks | `pylint app --enable=all` | 9.79/10 | 13 × R0903, 4 × E1136 suppressions, 1 × W0718 suppression (informational) |
| SA-5 | Test suite (commit `8d510ed`) | `pylint --recursive=y tests` with the app configuration and the test path added | 8.38/10 | 118 × C0116, 1 × W0621, 1 × R1710 |
| SA-6 | Test suite after CA-02 to CA-04 | `pylint --recursive=y tests --rcfile=tests/.pylintrc` | 10.00/10 | 0 |

## Triage

| ID | Finding | Location | Classification | Action |
|---|---|---|---|---|
| F-01 | E1136 `Value 'Mapped' is unsubscriptable` (27×) and `'sessionmaker' is unsubscriptable` (1×) | `infrastructure/db/models.py`, `infrastructure/db/session.py` | **False positive.** `Mapped[int]` and `sessionmaker[Session]` are the documented SQLAlchemy 2.x generic types; the code runs and all tests pass. | CA-01: disabled per file (not globally) with a comment giving the reason, so the check stays active everywhere else. |
| F-02 | W0621 `Redefining name 'pdf_bytes' from outer scope` | `tests/report_fakes.py:93` | **Fixed.** The helper function and the `extract(pdf_bytes)` parameter had the same name, so the parameter hid the helper inside the method. | CA-02: helper renamed to `fake_pdf`. The parameter keeps the interface name. |
| F-03 | R1710 `inconsistent-return-statements` | `tests/test_reports_api.py:33` | **Fixed.** `_wait_until_finished` returned a value on one path and fell off the end after `pytest.fail` on the other. | CA-03: the function now ends with an explicit `raise AssertionError`. |
| F-04 | C0116 `missing-function-docstring` (118×) | all `tests/test_*.py` | **Justified (configuration).** Test names state the behaviour checked (e.g. `test_one_byte_over_the_limit_is_rejected`); module docstrings name the requirement IDs. | CA-04: separate `tests/.pylintrc` disables C0116 for tests only; CI now lints the tests too. |
| F-05 | R0903 `too-few-public-methods` (13×) | SQLAlchemy row classes, interfaces, adapters | **Justified (configuration).** Rows, one-method interfaces (`TextExtractor`) and adapters are meant to be small (Interface Segregation). | Disabled in `.pylintrc` with a comment (from Day 1). |
| F-06 | W0718 `broad-exception-caught` (suppressed) | `services/report_service.py:180` | **Justified.** The worker's outer boundary must survive any error in one report (NFR-03); the traceback is logged and the report is marked failed. Specific errors are caught first. | Kept, with an inline justification. Checklist item C5 of Fagan inspection INS-01 covers it. |
| F-07 | Configuration decision (not a reported finding): `max-attributes=10` | `.pylintrc` | **Justified (configuration).** `LabReport` mirrors its 10 database columns; set when M4 was added. | Comment in `.pylintrc`. |

No finding was deferred.
