"""Hybrid Multimodal Search Studio backend.

Text/transcript search: BGE-M3 dense+sparse embedding -> Qdrant weighted RRF
-> BAAI/bge-reranker-v2-m3 cross-encoder re-scoring of the merged candidates.

Natural-language acoustic soundscape search: CLAP text embedding -> dense-only
Qdrant query against the acoustic_events collection (CLAP has no natural
sparse counterpart at query time; the sparse side of that collection is
populated from AST labels at index time only).
"""

from sonavault.adapters.sidecars import nlp_client, speech_client
from sonavault.adapters.vector import qdrant_repo

RERANK_CANDIDATE_POOL = 30


async def hybrid_text_search(
    *,
    query: str,
    collection: str,
    limit: int,
    max_tier: int,
    sanctuary_scopes: list[str],
    full_access: bool,
    rerank: bool,
) -> list[dict]:
    embeddings = await nlp_client.embed_bge_m3([query])
    embedding = embeddings[0]

    candidates = await qdrant_repo.hybrid_search(
        collection,
        dense_vector=embedding.dense,
        sparse_indices=embedding.sparse.indices,
        sparse_values=embedding.sparse.values,
        limit=RERANK_CANDIDATE_POOL if rerank else limit,
        max_tier=max_tier,
        sanctuary_scopes=sanctuary_scopes,
        full_access=full_access,
    )

    if not rerank or not candidates:
        return [
            {
                "asset_sha256": c.payload["asset_sha256"],
                "score": c.score,
                "rerank_score": None,
                "payload": c.payload,
            }
            for c in candidates[:limit]
        ]

    documents = [c.payload.get("text", "") for c in candidates]
    rerank_result = await nlp_client.rerank(query, documents)
    scored = sorted(
        zip(candidates, rerank_result.results, strict=True),
        key=lambda pair: pair[1].score,
        reverse=True,
    )
    return [
        {
            "asset_sha256": cand.payload["asset_sha256"],
            "score": cand.score,
            "rerank_score": rr.score,
            "payload": cand.payload,
        }
        for cand, rr in scored[:limit]
    ]


async def acoustic_text_search(
    *, query: str, limit: int, max_tier: int, sanctuary_scopes: list[str], full_access: bool
) -> list[dict]:
    clap_embedding = await speech_client.embed_clap_text(query)
    client = qdrant_repo.get_client()

    query_filter = qdrant_repo.rbac_filter(
        max_tier=max_tier, sanctuary_scopes=sanctuary_scopes, full_access=full_access
    )
    result = await client.query_points(
        collection_name="acoustic_events",
        query=clap_embedding.embedding,
        using=qdrant_repo.COLLECTIONS["acoustic_events"]["dense"],
        limit=limit,
        query_filter=query_filter,
    )
    return [
        {
            "asset_sha256": p.payload["asset_sha256"],
            "score": p.score,
            "rerank_score": None,
            "payload": p.payload,
        }
        for p in result.points
    ]


async def debug_hybrid_text_search(
    *,
    query: str,
    collection: str,
    limit: int,
    max_tier: int,
    sanctuary_scopes: list[str],
    full_access: bool,
) -> dict:
    embeddings = await nlp_client.embed_bge_m3([query])
    embedding = embeddings[0]

    dense_points = await qdrant_repo.search_dense_only(
        collection,
        dense_vector=embedding.dense,
        limit=limit,
        max_tier=max_tier,
        sanctuary_scopes=sanctuary_scopes,
        full_access=full_access,
    )

    sparse_points = await qdrant_repo.search_sparse_only(
        collection,
        sparse_indices=embedding.sparse.indices,
        sparse_values=embedding.sparse.values,
        limit=limit,
        max_tier=max_tier,
        sanctuary_scopes=sanctuary_scopes,
        full_access=full_access,
    )

    rrf_points = await qdrant_repo.hybrid_search(
        collection,
        dense_vector=embedding.dense,
        sparse_indices=embedding.sparse.indices,
        sparse_values=embedding.sparse.values,
        limit=limit,
        max_tier=max_tier,
        sanctuary_scopes=sanctuary_scopes,
        full_access=full_access,
    )

    by_id: dict[str, dict] = {}

    for rank, p in enumerate(dense_points, 1):
        pid = str(p.id)
        if pid not in by_id:
            by_id[pid] = {
                "point_id": pid,
                "asset_sha256": p.payload.get("asset_sha256", ""),
                "text": p.payload.get("text"),
                "payload": p.payload,
            }
        by_id[pid]["dense_score"] = float(p.score)
        by_id[pid]["dense_rank"] = rank

    for rank, p in enumerate(sparse_points, 1):
        pid = str(p.id)
        if pid not in by_id:
            by_id[pid] = {
                "point_id": pid,
                "asset_sha256": p.payload.get("asset_sha256", ""),
                "text": p.payload.get("text"),
                "payload": p.payload,
            }
        by_id[pid]["sparse_score"] = float(p.score)
        by_id[pid]["sparse_rank"] = rank

    for rank, p in enumerate(rrf_points, 1):
        pid = str(p.id)
        if pid not in by_id:
            by_id[pid] = {
                "point_id": pid,
                "asset_sha256": p.payload.get("asset_sha256", ""),
                "text": p.payload.get("text"),
                "payload": p.payload,
            }
        by_id[pid]["rrf_score"] = float(p.score)
        by_id[pid]["rrf_rank"] = rank

    items = list(by_id.values())
    if items:
        docs = [item.get("text") or "" for item in items]
        rerank_result = await nlp_client.rerank(query, docs)
        for idx, res in enumerate(rerank_result.results):
            items[idx]["rerank_score"] = float(res.score)

        sorted_items = sorted(
            items,
            key=lambda x: x.get("rerank_score") if x.get("rerank_score") is not None else -999.0,
            reverse=True,
        )
        for final_rank, item in enumerate(sorted_items, 1):
            item["rerank_rank"] = final_rank
        items = sorted_items

    return {
        "query": query,
        "collection": collection,
        "total_candidates": len(items),
        "items": items,
    }
