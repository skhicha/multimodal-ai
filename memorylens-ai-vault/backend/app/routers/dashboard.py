from __future__ import annotations

import os
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import CurrentUser, get_current_user
from app.db import db_cursor
from app.services.pipeline import reindex_all

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class UploadsByDay(BaseModel):
    date: str
    count: int


class TypeSplit(BaseModel):
    media_type: str
    count: int


class TagCount(BaseModel):
    tag: str
    count: int


class MapHotspot(BaseModel):
    media_id: str
    filename: str
    lat: float
    lon: float


class DashboardSummary(BaseModel):
    total_media: int
    total_photos: int
    total_videos: int
    total_faces: int
    total_with_gps: int
    uploads_by_day: List[UploadsByDay]
    type_split: List[TypeSplit]
    tag_distribution: List[TagCount]
    map_hotspots: List[MapHotspot]
    # Only populated when the caller is an admin: a system-wide summary
    # across all users, shown alongside their own stats above.
    is_admin: bool = False
    system_total_users: Optional[int] = None
    system_total_media: Optional[int] = None


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(current_user: CurrentUser = Depends(get_current_user)) -> DashboardSummary:
    uid = current_user.id
    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM media WHERE user_id = ?", (uid,))
        total_media = cur.fetchone()["c"]

        cur.execute("SELECT media_type, COUNT(*) AS c FROM media WHERE user_id = ? GROUP BY media_type", (uid,))
        type_rows = cur.fetchall()
        type_split = [TypeSplit(media_type=r["media_type"], count=r["c"]) for r in type_rows]
        total_photos = next((r["c"] for r in type_rows if r["media_type"] == "photo"), 0)
        total_videos = next((r["c"] for r in type_rows if r["media_type"] == "video"), 0)

        cur.execute("SELECT COALESCE(SUM(face_count), 0) AS c FROM media WHERE user_id = ?", (uid,))
        total_faces = cur.fetchone()["c"]

        cur.execute(
            "SELECT COUNT(*) AS c FROM media WHERE user_id = ? AND gps_lat IS NOT NULL AND gps_lon IS NOT NULL",
            (uid,),
        )
        total_with_gps = cur.fetchone()["c"]

        cur.execute(
            "SELECT date(created_at) AS d, COUNT(*) AS c FROM media WHERE user_id = ? GROUP BY d ORDER BY d",
            (uid,),
        )
        uploads_by_day = [UploadsByDay(date=r["d"], count=r["c"]) for r in cur.fetchall()]

        cur.execute(
            "SELECT tag, COUNT(*) AS c FROM tags WHERE media_id IN (SELECT id FROM media WHERE user_id = ?) "
            "GROUP BY tag ORDER BY c DESC LIMIT 20",
            (uid,),
        )
        tag_distribution = [TagCount(tag=r["tag"], count=r["c"]) for r in cur.fetchall()]

        cur.execute(
            "SELECT id, filename, gps_lat, gps_lon FROM media "
            "WHERE user_id = ? AND gps_lat IS NOT NULL AND gps_lon IS NOT NULL",
            (uid,),
        )
        map_hotspots = [
            MapHotspot(media_id=r["id"], filename=r["filename"], lat=r["gps_lat"], lon=r["gps_lon"])
            for r in cur.fetchall()
        ]

        system_total_users = None
        system_total_media = None
        if current_user.role == "admin":
            cur.execute("SELECT COUNT(*) AS c FROM users")
            system_total_users = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM media")
            system_total_media = cur.fetchone()["c"]

    return DashboardSummary(
        total_media=total_media,
        total_photos=total_photos,
        total_videos=total_videos,
        total_faces=total_faces,
        total_with_gps=total_with_gps,
        uploads_by_day=uploads_by_day,
        type_split=type_split,
        tag_distribution=tag_distribution,
        map_hotspots=map_hotspots,
        is_admin=current_user.role == "admin",
        system_total_users=system_total_users,
        system_total_media=system_total_media,
    )


class SettingsOut(BaseModel):
    llm_provider: str
    anthropic_key_configured: bool
    whisper_model: str


@router.get("/settings", response_model=SettingsOut)
def get_settings(current_user: CurrentUser = Depends(get_current_user)) -> SettingsOut:
    return SettingsOut(
        llm_provider=os.environ.get("LLM_PROVIDER", "mock"),
        anthropic_key_configured=bool(os.environ.get("ANTHROPIC_API_KEY")),
        whisper_model=os.environ.get("WHISPER_MODEL", "tiny"),
    )


class ReindexOut(BaseModel):
    reindexed: int


@router.post("/reindex", response_model=ReindexOut)
def reindex(current_user: CurrentUser = Depends(get_current_user)) -> ReindexOut:
    count = reindex_all()
    return ReindexOut(reindexed=count)
