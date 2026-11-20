# Auralis

A web-based diabetes self-management system for patients: log glucose readings, see patterns, log meals and their effect on glucose, and get lab reports explained in plain language.

Joint semester project for SE423 (Software Construction and Development) and SE431 (Software Quality Assurance), GIKI. Team: Code Wizards.

| Module | Owner | Status (Milestone 2) |
|---|---|---|
| Core architecture (settings, errors, database, CI) | Muhammad Hamid Quyyum | Done |
| M1 Glucose Logging | Muhammad Abubakar | Done |
| M2 Health Trend Analysis (Strategy pattern) | Muhammad Abubakar | Done |
| M3 Meal and Nutrition Logging | Ahmad Uzair Shah | In progress (`feature/meal-logging`) |
| M4 Medical Report Analyzer (Factory Method, Adapter, async workers) | Muhammad Hamid Quyyum | Done |
| React frontend | All members | Planned for Milestone 3 |

## Tech stack

- Backend: Python, FastAPI, SQLAlchemy, SQLite
- Frontend: React (Vite, Tailwind CSS, shadcn/ui, Recharts)
- Quality: pytest, pytest-cov, Pylint, GitHub Actions

## Setup

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy ..\.env.example ..\.env    # macOS/Linux: cp ../.env.example ../.env
uvicorn app.main:create_app --factory --reload
```

The API runs at http://localhost:8000/api and the interactive docs at http://localhost:8000/docs.
`GROQ_API_KEY` in `.env` is optional; without it, lab reports use the template explanation.

### Tests and static analysis

```bash
cd backend
pytest --cov=app --cov-report=term-missing
pylint app --fail-under=8.0
pylint --recursive=y tests --rcfile=tests/.pylintrc   # once the static-analysis fixes are merged
```

CI (`.github/workflows/ci.yml`) runs the same checks on every push and pull request.

### Frontend (Milestone 3)

`frontend/` is still empty. Once it is set up:

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

## Project structure

```
backend/
  app/
    api/             FastAPI routers, Pydantic schemas, dependencies, error handlers
    core/            settings, logging, exception hierarchy
    domain/          dataclasses, enums, interfaces (no framework imports)
    services/        business rules of the modules
    infrastructure/  SQLAlchemy repositories, PyMuPDF and Groq adapters, explanation factory
    main.py          application factory (composition root)
  tests/             pytest suite; *_fakes.py hold in-memory test doubles; fixtures/ holds sample PDFs
frontend/            React app (Milestone 3)
docs/
  ai-usage-log.md    AI usage log (required by the course guidelines)
  m2/                Milestone 2 design and quality documents (thread-safety strategy)
```

Dependencies point inwards: `api -> services -> domain <- infrastructure`.

## Branch strategy

- `main`: protected; updated only at milestones through a reviewed pull request from `dev`, and tagged (`m1-baseline`, `m2-baseline`, `m3-final`).
- `dev`: integration branch; must build and pass CI.
- `feature/<module>-<short-desc>`: one branch per task, merged into `dev` by pull request after review by another member, using merge commits (no squash).
- `fix/<short-desc>`: defect fixes, same rules as features.
- `docs/<short-desc>`: documentation-only changes, same rules.
- `main` and `dev` are protected by rulesets: a pull request, one approval and passing CI are required, and force pushes and deletion are blocked. GitHub's default branch is `main`, so set the pull request's base to `dev` by hand.

Every feature is committed test-first: a failing test (`test:`), the code that makes it pass (`feat:`), then any clean-up (`refactor:`).
