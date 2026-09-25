"""Outcomes API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.outcome_service import (
    build_outcomes,
    grow_outcomes,
    resolve_outcomes,
)

router = APIRouter(prefix="/api/outcomes", tags=["outcomes"])


@router.get("")
def outcomes(db: Session = Depends(get_db)):
    return build_outcomes(db)


@router.get("/resolve")
def resolve(db: Session = Depends(get_db)):
    return resolve_outcomes(db)


@router.get("/grow")
def grow(db: Session = Depends(get_db)):
    return grow_outcomes(db)
