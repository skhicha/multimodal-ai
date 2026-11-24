"""FTS5-backed full-text search over filenames, tags and transcripts."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from app.db import db_cursor


@dataclass
class SearchHit:
    media_id: str
    source: str  # "filename" | "tag" | "transcript"
    segment_start: Optional[float]
    text: str
    snippet: str


_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "show", "me", "my", "any",
    "of", "in", "on", "at", "to", "for", "with", "what", "whats", "where",
    "who", "do", "does", "did", "i", "have", "has", "can", "you", "find",
    "about", "it", "there",
}


def _fts_escape(q: str, mode: str = "and") -> str:
    """Builds a safe FTS5 MATCH query: strips characters FTS5's query syntax
    treats specially and joins the remaining tokens with a trailing prefix
    wildcard. mode="and" (default, used by the literal Search page) requires
    every token to match -- precise. mode="or" (used by Ask AI, since a
    natural-language question like "Show me outdoor photos" should still
    find a media item tagged just "outdoor") requires only one -- recall
    over precision, with common stopwords dropped so they don't dilute it."""
    tokens = re.findall(r"[A-Za-z0-9_]+", q)
    if mode == "or":
        tokens = [t for t in tokens if t.lower() not in _STOPWORDS] or tokens
    if not tokens:
        return ""
    joiner = " OR " if mode == "or" else " AND "
    return joiner.join(f'"{t}"*' for t in tokens)


def reindex_media(media_id: str, filename: str, tags: List[str], transcript, captions=None) -> None:
    """Rebuilds the FTS rows for one media item: filename + tags +
    transcript segments (what was SAID) + visual captions (what the photo
    or a video's keyframes actually SHOW, from services/captioning.py --
    this is what lets Search/Ask AI answer questions about silent footage
    and photos, neither of which a transcript can ever cover)."""
    with db_cursor() as cur:
        cur.execute("DELETE FROM search_index WHERE media_id = ?", (media_id,))
        cur.execute(
            "INSERT INTO search_index (media_id, source, segment_start, text) VALUES (?, 'filename', NULL, ?)",
            (media_id, filename),
        )
        for tag in tags:
            cur.execute(
                "INSERT INTO search_index (media_id, source, segment_start, text) VALUES (?, 'tag', NULL, ?)",
                (media_id, tag),
            )
        for seg in transcript or []:
            cur.execute(
                "INSERT INTO search_index (media_id, source, segment_start, text) VALUES (?, 'transcript', ?, ?)",
                (media_id, seg.start, seg.text),
            )
        for cap in captions or []:
            cur.execute(
                "INSERT INTO search_index (media_id, source, segment_start, text) VALUES (?, 'caption', ?, ?)",
                (media_id, cap.frame_time, cap.caption),
            )


def search(query: str, limit: int = 40, user_id: Optional[str] = None, mode: str = "and") -> List[SearchHit]:
    match = _fts_escape(query, mode=mode)
    if not match:
        return []
    with db_cursor() as cur:
        if user_id:
            cur.execute(
                """
                SELECT si.media_id, si.source, si.segment_start, si.text,
                       snippet(search_index, 3, '<mark>', '</mark>', '…', 12) AS snip
                FROM search_index si
                JOIN media m ON m.id = si.media_id
                WHERE search_index MATCH ? AND m.user_id = ?
                ORDER BY rank
                LIMIT ?
                """,
                (match, user_id, limit),
            )
        else:
            cur.execute(
                """
                SELECT media_id, source, segment_start, text,
                       snippet(search_index, 3, '<mark>', '</mark>', '…', 12) AS snip
                FROM search_index
                WHERE search_index MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (match, limit),
            )
        rows = cur.fetchall()
    return [
        SearchHit(
            media_id=r["media_id"],
            source=r["source"],
            segment_start=r["segment_start"],
            text=r["text"],
            snippet=r["snip"],
        )
        for r in rows
    ]
