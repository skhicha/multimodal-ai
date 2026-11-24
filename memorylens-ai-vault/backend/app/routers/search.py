from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.auth import CurrentUser, get_current_user
from app.db import db_cursor
from app.services.search import search as fts_search

router = APIRouter(prefix="/api/search", tags=["search"])


class SearchResultOut(BaseModel):
    media_id: str
    filename: str
    media_type: str
    thumb_url: Optional[str]
    source: str
    segment_start: Optional[float]
    snippet: str


@router.get("", response_model=List[SearchResultOut])
def search_media(
    q: str = Query(..., min_length=1), current_user: CurrentUser = Depends(get_current_user)
) -> List[SearchResultOut]:
    hits = fts_search(q, user_id=current_user.id)
    out: List[SearchResultOut] = []
    for hit in hits:
        with db_cursor() as cur:
            cur.execute(
                "SELECT filename, media_type, thumb_path FROM media WHERE id = ? AND user_id = ?",
                (hit.media_id, current_user.id),
            )
            row = cur.fetchone()
        if not row:
            continue
        out.append(
            SearchResultOut(
                media_id=hit.media_id,
                filename=row["filename"],
                media_type=row["media_type"],
                thumb_url=f"/api/media/{hit.media_id}/thumbnail" if row["thumb_path"] else None,
                source=hit.source,
                segment_start=hit.segment_start,
                snippet=hit.snippet,
            )
        )
    return out
