# Auralis

A web-based diabetes self-management system for patients: log glucose readings, see patterns, log meals and their effect on glucose, and get lab reports explained in plain language.

Joint semester project for SE423 (Software Construction and Development) and SE431 (Software Quality Assurance), GIKI. Team: Code Wizards.

| Module | Owner |
|---|---|
| M1 Glucose Logging | Muhammad Abubakar |
| M2 Health Trend Analysis | Muhammad Abubakar |
| M3 Meal and Nutrition Logging | Ahmad Uzair Shah |
| M4 Medical Report Analyzer | Muhammad Hamid Quyyum |

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

The API runs at http://localhost:8000 and the interactive docs at http://localhost:8000/docs.
`GROQ_API_KEY` in `.env` is optional; without it, lab reports use the template explanation.

### Tests and static analysis

```bash
cd backend
pytest --cov=app --cov-report=term-missing
pylint app
```

### Frontend

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

## Project structure

```
backend/
  app/
    api/             FastAPI routers, schemas, dependencies, error handlers
    core/            settings, logging, exception hierarchy
    domain/          entities, value objects, interfaces (no framework imports)
    services/        business logic of the four modules
    infrastructure/  SQLAlchemy repositories, PyMuPDF and Groq adapters
    main.py          application factory
  tests/
frontend/
docs/
```

Dependencies point inwards: `api -> services -> domain <- infrastructure`.

## Branch strategy

- `main`: protected; updated only at milestones through a reviewed pull request from `dev`, and tagged (`m1-baseline`, `m2-baseline`, `m3-final`).
- `dev`: integration branch; must build and pass CI.
- `feature/<module>-<short-desc>`: one branch per task, merged into `dev` by pull request after review by another member, using merge commits (no squash).
- `fix/<short-desc>`: defect fixes, same rules as features.

Every feature is committed test-first: a failing test (`test:`), the code that makes it pass (`feat:`), then any clean-up (`refactor:`).
