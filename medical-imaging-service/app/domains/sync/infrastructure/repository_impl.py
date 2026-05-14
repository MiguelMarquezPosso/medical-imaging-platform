"""Repository implementations for the sync domain."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.sync.domain.entities import SyncRecord, SyncStatus
from app.domains.sync.infrastructure.models import AuditLogORM, SyncRecordORM


class SqlSyncRecordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, record: SyncRecord) -> None:
        orm = SyncRecordORM(
            id=record.id,
            device_id=record.device_id,
            user_id=record.user_id,
            sha256=record.sha256,
            size_bytes=record.size_bytes,
            status=record.status.value,
            sop_instance_uid=record.sop_instance_uid,
            study_instance_uid=record.study_instance_uid,
            series_instance_uid=record.series_instance_uid,
            storage_uri=record.storage_uri,
            error=record.error,
            created_at=record.created_at,
        )
        self.session.add(orm)
        await self.session.flush()

    async def update(self, record: SyncRecord) -> None:
        orm = await self.session.get(SyncRecordORM, record.id)
        if not orm:
            return
        orm.status = record.status.value
        orm.storage_uri = record.storage_uri
        orm.error = record.error
        orm.sop_instance_uid = record.sop_instance_uid
        orm.study_instance_uid = record.study_instance_uid
        orm.series_instance_uid = record.series_instance_uid
        await self.session.flush()

    async def exists_by_sha(self, sha256: str) -> bool:
        result = await self.session.execute(
            select(SyncRecordORM.id).where(SyncRecordORM.sha256 == sha256)
        )
        return result.scalar_one_or_none() is not None

    async def list_recent(self, *, limit: int = 100, offset: int = 0) -> list[SyncRecord]:
        result = await self.session.execute(
            select(SyncRecordORM)
            .order_by(SyncRecordORM.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = result.scalars().all()
        return [
            SyncRecord(
                id=r.id,
                device_id=r.device_id,
                user_id=r.user_id,
                sha256=r.sha256,
                size_bytes=r.size_bytes,
                status=SyncStatus(r.status),
                sop_instance_uid=r.sop_instance_uid,
                study_instance_uid=r.study_instance_uid,
                series_instance_uid=r.series_instance_uid,
                storage_uri=r.storage_uri,
                error=r.error,
                created_at=r.created_at,
            )
            for r in rows
        ]


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        *,
        actor: str | None,
        action: str,
        target: str | None = None,
        request_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        payload: dict | None = None,
    ) -> None:
        entry = AuditLogORM(
            actor=actor,
            action=action,
            target=target,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload=payload,
        )
        self.session.add(entry)
        await self.session.flush()
