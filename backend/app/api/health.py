"""Health check used by the frontend and for demos."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    """Report that the API is up and the database answers."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
