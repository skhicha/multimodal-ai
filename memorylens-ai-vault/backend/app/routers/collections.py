"""
Collections (albums): a named grouping of a user's own media, in one of two
modes -- see app/db.py's schema comment on the `collections` table.
"""
from __future__ import annotations

import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import CurrentUser, require_permission
from app.db import db_cursor
from app.routers.media import MediaOut, _row_to_media_out

router = APIRouter(prefix="/api/collections", tags=["collections"])


class FilterIn(BaseModel):
    media_type: Optional[str] = None
    tag: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None


class CollectionIn(BaseModel):
    name: str
    description: Optional[str] = None
    filter: Optional[FilterIn] = None


class CollectionOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    is_smart: bool
    filter: Optional[FilterIn] = None
    item_count: int
    created_at: str


def _resolve_smart_items(cur, user_id: str, filter_json: str) -> List:
    """Re-runs the same filter Library already applies to GET /api/media,
    so a smart collection's membership always reflects the vault as it is
    right now rather than a stale snapshot taken when it was created."""
    f = json.loads(filter_json)
    clauses = ["user_id = ?", "deleted_at IS NULL"]
    params: list = [user_id]
    if f.get("media_type"):
        clauses.append("media_type = ?")
        params.append(f["media_type"])
    if f.get("date_from"):
        clauses.append("created_at >= ?")
        params.append(f["date_from"])
    if f.get("date_to"):
        clauses.append("created_at <= ?")
        params.append(f["date_to"])
    if f.get("tag"):
        clauses.append("id IN (SELECT media_id FROM tags WHERE tag = ?)")
        params.append(f["tag"])
    where = f"WHERE {' AND '.join(clauses)}"
    cur.execute(f"SELECT * FROM media {where} ORDER BY created_at DESC", params)
    return cur.fetchall()


def _item_count(cur, collection_id: str, user_id: str, filter_json: Optional[str]) -> int:
    if filter_json:
        return len(_resolve_smart_items(cur, user_id, filter_json))
    return cur.execute(
        "SELECT COUNT(*) c FROM collection_items ci JOIN media m ON m.id = ci.media_id "
        "WHERE ci.collection_id = ? AND m.deleted_at IS NULL",
        (collection_id,),
    ).fetchone()["c"]


def _row_to_collection_out(row, item_count: int) -> CollectionOut:
    filt = json.loads(row["filter_json"]) if row["filter_json"] else None
    return CollectionOut(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        is_smart=bool(row["filter_json"]),
        filter=FilterIn(**filt) if filt else None,
        item_count=item_count,
        created_at=row["created_at"],
    )


@router.get("", response_model=List[CollectionOut])
def list_collections(current_user: CurrentUser = Depends(require_permission("collections.view"))) -> List[CollectionOut]:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM collections WHERE user_id = ? ORDER BY created_at DESC", (current_user.id,))
        rows = cur.fetchall()
        out = [_row_to_collection_out(r, _item_count(cur, r["id"], current_user.id, r["filter_json"])) for r in rows]
    return out


@router.post("", response_model=CollectionOut)
def create_collection(
    body: CollectionIn, current_user: CurrentUser = Depends(require_permission("collections.create"))
) -> CollectionOut:
    if not body.name.strip():
        raise HTTPException(400, "Collection name is required")
    collection_id = uuid.uuid4().hex[:16]
    filter_json = json.dumps(body.filter.model_dump()) if body.filter else None
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO collections (id, user_id, name, description, filter_json) VALUES (?, ?, ?, ?, ?)",
            (collection_id, current_user.id, body.name.strip(), body.description, filter_json),
        )
        cur.execute("SELECT * FROM collections WHERE id = ?", (collection_id,))
        row = cur.fetchone()
        count = _item_count(cur, collection_id, current_user.id, filter_json)
    return _row_to_collection_out(row, count)


def _get_owned_collection(cur, collection_id: str, user_id: str):
    cur.execute("SELECT * FROM collections WHERE id = ? AND user_id = ?", (collection_id, user_id))
    return cur.fetchone()


@router.get("/{collection_id}", response_model=CollectionOut)
def get_collection(
    collection_id: str, current_user: CurrentUser = Depends(require_permission("collections.view"))
) -> CollectionOut:
    with db_cursor() as cur:
        row = _get_owned_collection(cur, collection_id, current_user.id)
        if not row:
            raise HTTPException(404, "Collection not found")
        count = _item_count(cur, collection_id, current_user.id, row["filter_json"])
    return _row_to_collection_out(row, count)


@router.get("/{collection_id}/items", response_model=List[MediaOut])
def list_collection_items(
    collection_id: str, current_user: CurrentUser = Depends(require_permission("collections.view"))
) -> List[MediaOut]:
    with db_cursor() as cur:
        row = _get_owned_collection(cur, collection_id, current_user.id)
        if not row:
            raise HTTPException(404, "Collection not found")
        if row["filter_json"]:
            media_rows = _resolve_smart_items(cur, current_user.id, row["filter_json"])
        else:
            cur.execute(
                "SELECT m.* FROM collection_items ci JOIN media m ON m.id = ci.media_id "
                "WHERE ci.collection_id = ? AND m.deleted_at IS NULL ORDER BY ci.added_at DESC",
                (collection_id,),
            )
            media_rows = cur.fetchall()
        out = []
        for m in media_rows:
            cur.execute("SELECT tag FROM tags WHERE media_id = ?", (m["id"],))
            tags = [r["tag"] for r in cur.fetchall()]
            out.append(_row_to_media_out(m, tags))
    return out


class RenameIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


@router.patch("/{collection_id}", response_model=CollectionOut)
def update_collection(
    collection_id: str, body: RenameIn, current_user: CurrentUser = Depends(require_permission("collections.edit"))
) -> CollectionOut:
    with db_cursor() as cur:
        row = _get_owned_collection(cur, collection_id, current_user.id)
        if not row:
            raise HTTPException(404, "Collection not found")
        if body.name is not None and not body.name.strip():
            raise HTTPException(400, "Collection name cannot be empty")
        cur.execute(
            "UPDATE collections SET name = COALESCE(?, name), description = COALESCE(?, description) WHERE id = ?",
            (body.name.strip() if body.name else None, body.description, collection_id),
        )
        cur.execute("SELECT * FROM collections WHERE id = ?", (collection_id,))
        row = cur.fetchone()
        count = _item_count(cur, collection_id, current_user.id, row["filter_json"])
    return _row_to_collection_out(row, count)


@router.delete("/{collection_id}")
def delete_collection(
    collection_id: str, current_user: CurrentUser = Depends(require_permission("collections.delete"))
) -> dict:
    with db_cursor() as cur:
        row = _get_owned_collection(cur, collection_id, current_user.id)
        if not row:
            raise HTTPException(404, "Collection not found")
        cur.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
    return {"ok": True}


class AddItemIn(BaseModel):
    media_id: str


@router.post("/{collection_id}/items")
def add_item(
    collection_id: str, body: AddItemIn, current_user: CurrentUser = Depends(require_permission("collections.edit"))
) -> dict:
    with db_cursor() as cur:
        row = _get_owned_collection(cur, collection_id, current_user.id)
        if not row:
            raise HTTPException(404, "Collection not found")
        if row["filter_json"]:
            raise HTTPException(400, "Can't manually add items to a smart collection -- edit its filter instead")
        media_row = cur.execute(
            "SELECT id FROM media WHERE id = ? AND user_id = ? AND deleted_at IS NULL",
            (body.media_id, current_user.id),
        ).fetchone()
        if not media_row:
            raise HTTPException(404, "Media not found")
        cur.execute(
            "INSERT OR IGNORE INTO collection_items (collection_id, media_id) VALUES (?, ?)",
            (collection_id, body.media_id),
        )
    return {"ok": True}


@router.delete("/{collection_id}/items/{media_id}")
def remove_item(
    collection_id: str, media_id: str, current_user: CurrentUser = Depends(require_permission("collections.edit"))
) -> dict:
    with db_cursor() as cur:
        row = _get_owned_collection(cur, collection_id, current_user.id)
        if not row:
            raise HTTPException(404, "Collection not found")
        cur.execute(
            "DELETE FROM collection_items WHERE collection_id = ? AND media_id = ?",
            (collection_id, media_id),
        )
    return {"ok": True}
