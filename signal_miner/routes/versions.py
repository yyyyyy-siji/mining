"""Dataset version management routes — isolate imports, pipeline runs, and assets."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select

from signal_miner.db import get_session_factory
from signal_miner.db.models import (
    DEFAULT_VERSION_ID,
    DatasetVersionRow,
    OpportunityRow,
    PainPointRow,
    PipelineRunRow,
    RawFeedbackRow,
    RequirementAssetRow,
    SignalRow,
    ThemeRow,
)
from signal_miner.models import new_id

router = APIRouter()


class CreateVersionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, description="版本名称")
    description: str = Field("", max_length=1000, description="版本备注/调研目标")


class UpdateVersionRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=1000)
    status: Literal["active", "archived"] | None = None


async def _ensure_default_version(session) -> None:
    row = await session.get(DatasetVersionRow, DEFAULT_VERSION_ID)
    if row is None:
        now = datetime.now(timezone.utc)
        session.add(
            DatasetVersionRow(
                id=DEFAULT_VERSION_ID,
                name="默认版本（历史数据）",
                description="系统内置默认版本，归档未指定版本的历史数据。",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        await session.flush()


async def _version_stats(session, version_id: str) -> dict:
    fb_count = (
        await session.execute(
            select(func.count()).where(RawFeedbackRow.version_id == version_id)
        )
    ).scalar() or 0
    sig_count = (
        await session.execute(
            select(func.count()).where(SignalRow.version_id == version_id)
        )
    ).scalar() or 0
    thm_count = (
        await session.execute(
            select(func.count()).where(ThemeRow.version_id == version_id)
        )
    ).scalar() or 0
    pp_count = (
        await session.execute(
            select(func.count()).where(PainPointRow.version_id == version_id)
        )
    ).scalar() or 0
    opp_count = (
        await session.execute(
            select(func.count()).where(OpportunityRow.version_id == version_id)
        )
    ).scalar() or 0
    req_count = (
        await session.execute(
            select(func.count()).where(RequirementAssetRow.version_id == version_id)
        )
    ).scalar() or 0

    src_rows = (
        await session.execute(
            select(RawFeedbackRow.source_type, func.count())
            .where(RawFeedbackRow.version_id == version_id)
            .group_by(RawFeedbackRow.source_type)
        )
    ).all()
    sources = {str(src): int(cnt) for src, cnt in src_rows}
    return {
        "feedback_count": int(fb_count),
        "signal_count": int(sig_count),
        "theme_count": int(thm_count),
        "pain_point_count": int(pp_count),
        "opportunity_count": int(opp_count),
        "requirement_count": int(req_count),
        "sources": sources,
    }


def _serialize_version(row: DatasetVersionRow, stats: dict) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description or "",
        "status": row.status,
        "is_default": row.id == DEFAULT_VERSION_ID,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "stats": stats,
    }


@router.get("/versions", summary="List dataset versions with per-version stats")
async def list_versions(include_archived: bool = True) -> dict:
    session_factory = get_session_factory()
    async with session_factory() as session:
        await _ensure_default_version(session)
        await session.commit()

        stmt = select(DatasetVersionRow).order_by(DatasetVersionRow.created_at.desc())
        if not include_archived:
            stmt = stmt.where(DatasetVersionRow.status == "active")
        rows = (await session.execute(stmt)).scalars().all()
        # Keep default version pinned at the bottom or sorted cleanly
        rows.sort(key=lambda r: (r.id == DEFAULT_VERSION_ID, -(r.created_at.timestamp() if r.created_at else 0)))

        items = []
        for row in rows:
            stats = await _version_stats(session, row.id)
            items.append(_serialize_version(row, stats))
        return {"versions": items, "default_version_id": DEFAULT_VERSION_ID}


@router.post("/versions", status_code=status.HTTP_201_CREATED, summary="Create a new dataset version")
async def create_version(body: CreateVersionRequest) -> dict:
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="版本名称不能为空。")
    session_factory = get_session_factory()
    async with session_factory() as session:
        await _ensure_default_version(session)
        now = datetime.now(timezone.utc)
        row = DatasetVersionRow(
            id=new_id("ver"),
            name=name,
            description=body.description.strip(),
            status="active",
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.commit()
        stats = await _version_stats(session, row.id)
        return _serialize_version(row, stats)


@router.patch("/versions/{version_id}", summary="Update a dataset version")
async def update_version(version_id: str, body: UpdateVersionRequest) -> dict:
    session_factory = get_session_factory()
    async with session_factory() as session:
        await _ensure_default_version(session)
        row = await session.get(DatasetVersionRow, version_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"版本 {version_id} 不存在。")
        if body.name is not None:
            cleaned = body.name.strip()
            if not cleaned:
                raise HTTPException(status_code=422, detail="版本名称不能为空。")
            row.name = cleaned
        if body.description is not None:
            row.description = body.description.strip()
        if body.status is not None:
            if version_id == DEFAULT_VERSION_ID and body.status == "archived":
                raise HTTPException(status_code=400, detail="默认版本不可归档。")
            row.status = body.status
        row.updated_at = datetime.now(timezone.utc)
        await session.commit()
        stats = await _version_stats(session, row.id)
        return _serialize_version(row, stats)


@router.delete("/versions/{version_id}", summary="Delete a dataset version and its scoped records")
async def delete_version(version_id: str) -> dict:
    if version_id == DEFAULT_VERSION_ID:
        raise HTTPException(status_code=400, detail="内置默认版本不可删除。")
    session_factory = get_session_factory()
    async with session_factory() as session:
        row = await session.get(DatasetVersionRow, version_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"版本 {version_id} 不存在。")

        for model in (
            RequirementAssetRow,
            OpportunityRow,
            PainPointRow,
            ThemeRow,
            SignalRow,
            RawFeedbackRow,
            PipelineRunRow,
        ):
            await session.execute(delete(model).where(model.version_id == version_id))
        await session.delete(row)
        await session.commit()
        return {"deleted": True, "version_id": version_id}
