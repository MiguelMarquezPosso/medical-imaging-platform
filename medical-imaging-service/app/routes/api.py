"""Global router — the single place where every domain router is registered.

To add a new domain:
  1. Build it under `app/domains/<name>/`
  2. Expose its router as `app.domains.<name>.<name>_router`
  3. Add a single `api_router.include_router(...)` line below

The rest of the project does not need to change.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.domains.instances import instances_router, stow_router
from app.domains.series import series_router
from app.domains.studies import studies_router
from app.domains.sync import sync_router
from app.routes.health import router as health_router

api_router = APIRouter()

api_router.include_router(health_router)

# Domain routers
api_router.include_router(studies_router)
api_router.include_router(series_router)
api_router.include_router(instances_router)
api_router.include_router(stow_router)
api_router.include_router(sync_router)
