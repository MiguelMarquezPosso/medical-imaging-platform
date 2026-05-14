"""Liveness and readiness probes (global)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_dicomweb_provider
from app.providers.dicomweb import DICOMwebProvider

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readiness(
    session: Annotated[AsyncSession, Depends(get_db)],
    dicomweb: Annotated[DICOMwebProvider, Depends(get_dicomweb_provider)],
) -> dict[str, object]:
    await session.execute(text("SELECT 1"))
    upstream_ok = await dicomweb.healthcheck()
    return {"status": "ready", "db": "ok", "dicomweb": "ok" if upstream_ok else "degraded"}
