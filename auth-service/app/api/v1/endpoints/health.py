"""Health and readiness probes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readiness(session: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ready"}
