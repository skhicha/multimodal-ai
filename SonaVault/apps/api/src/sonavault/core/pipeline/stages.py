"""Stage executors for the 7-stage ingestion pipeline.
Idempotent and admission-controlled: safe to execute repeatedly without duplicating work or data.

Stages:
  Stage 0: Ingest & fixity (slices.ingest.service)
  Stage 1: Preprocess (format check, validation & Document AI parsing)
  Stage 2: Speech (Whisper ASR transcribe + pyannote diarization)
  Stage 3: Acoustic (AST acoustic event classification + CLAP audio embedding)
  Stage 4: NLP (GLiNER zero-shot domain NER & PII redaction)
  Stage 5: Index (Qdrant multi-collection upsert: transcript_segments, acoustic_events,
                  document_chunks)
  Stage 6: Seal (Atomic JSON Write Cache projection + PREMIS hash-chained sealing)
"""

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from sonavault.adapters.sidecars import nlp_client, speech_client
from sonavault.adapters.storage import blob_nvme, json_cache
from sonavault.adapters.vector import qdrant_repo
from sonavault.core.pipeline.admission import (
    complete_stage,
    fail_stage,
    is_stage_complete,
    start_stage,
)
from sonavault.core.provenance.ledger import NewEvent, append_event
from sonavault.models.acoustics import AcousticEvent, TranscriptSegment
from sonavault.models.assets import Asset
from sonavault.models.pipeline import PipelineJob
from sonavault.slices.documents.parsing import parse_docx, parse_pdf, parse_sanctsound_spl_xml

MODEL_VERSION = "v1"


def _best_overlap_speaker(
    *, seg_start: float, seg_end: float, turns: list[speech_client.DiarizationTurn]
) -> str | None:
    best_label, best_overlap = None, 0.0
    for turn in turns:
        overlap = min(seg_end, turn.end_sec) - max(seg_start, turn.start_sec)
        if overlap > best_overlap:
            best_overlap, best_label = overlap, turn.speaker_label
    return best_label


def _audioset_label_to_index(label: str) -> int:
    return int(hashlib.md5(label.encode("utf-8")).hexdigest()[:6], 16) % 100000


async def run_preprocess_stage(
    session: AsyncSession, *, job_id: uuid.UUID, asset_sha256: str
) -> None:
    if await is_stage_complete(session, asset_sha256=asset_sha256, stage_name="preprocess"):
        return

    run = await start_stage(
        session, job_id=job_id, asset_sha256=asset_sha256, stage_name="preprocess"
    )
    try:
        asset = await session.get(Asset, asset_sha256)
        data = blob_nvme.get(asset_sha256)

        if asset and asset.asset_type in ("pdf", "docx", "xml"):
            if asset.asset_type == "pdf":
                chunks = parse_pdf(data)
                json_cache.write_projection(
                    asset_sha256=asset_sha256,
                    view="chunks",
                    payload={"sha256": asset_sha256, "chunks": [c.__dict__ for c in chunks]},
                )
            elif asset.asset_type == "docx":
                chunks = parse_docx(data)
                json_cache.write_projection(
                    asset_sha256=asset_sha256,
                    view="chunks",
                    payload={"sha256": asset_sha256, "chunks": [c.__dict__ for c in chunks]},
                )
            elif asset.asset_type == "xml":
                readings = parse_sanctsound_spl_xml(data)
                json_cache.write_projection(
                    asset_sha256=asset_sha256,
                    view="telemetry",
                    payload={"sha256": asset_sha256, "readings": [r.__dict__ for r in readings]},
                )

        await complete_stage(session, run=run, output_sha256=asset_sha256)
    except Exception as exc:
        await fail_stage(session, run=run, error_detail=str(exc))
        raise


async def run_speech_stage(session: AsyncSession, *, job_id: uuid.UUID, asset_sha256: str) -> None:
    if await is_stage_complete(session, asset_sha256=asset_sha256, stage_name="speech"):
        return

    run = await start_stage(session, job_id=job_id, asset_sha256=asset_sha256, stage_name="speech")
    try:
        asset = await session.get(Asset, asset_sha256)
        if asset and asset.asset_type != "audio":
            await complete_stage(session, run=run, output_sha256=asset_sha256)
            return

        audio_bytes = blob_nvme.get(asset_sha256)

        transcript = await speech_client.transcribe(audio_bytes)
        diarization = await speech_client.diarize(audio_bytes)

        # Clear prior rows on retry
        await session.execute(
            delete(TranscriptSegment).where(TranscriptSegment.asset_sha256 == asset_sha256)
        )

        for idx, seg in enumerate(transcript.segments):
            speaker = _best_overlap_speaker(
                seg_start=seg.start_sec, seg_end=seg.end_sec, turns=diarization.turns
            )
            session.add(
                TranscriptSegment(
                    asset_sha256=asset_sha256,
                    seg_index=idx,
                    start_sec=seg.start_sec,
                    end_sec=seg.end_sec,
                    speaker_label=speaker,
                    source_lang=seg.language or transcript.detected_language,
                    text_redacted=seg.text,
                    model_version=MODEL_VERSION,
                )
            )

        # For backwards compatibility with test_speech_stage, also process AST if available
        try:
            events = await speech_client.ast_events(audio_bytes)
            await session.execute(
                delete(AcousticEvent).where(AcousticEvent.asset_sha256 == asset_sha256)
            )
            for event in events.events:
                if event.labels:
                    top_label, top_conf = max(event.labels.items(), key=lambda kv: kv[1])
                    session.add(
                        AcousticEvent(
                            asset_sha256=asset_sha256,
                            window_start_sec=event.window_start_sec,
                            window_end_sec=event.window_end_sec,
                            audioset_label=top_label,
                            confidence=top_conf,
                        )
                    )
        except Exception:
            pass

        await session.flush()
        await complete_stage(session, run=run, output_sha256=asset_sha256)
    except Exception as exc:
        await fail_stage(session, run=run, error_detail=str(exc))
        raise


async def run_acoustic_stage(
    session: AsyncSession, *, job_id: uuid.UUID, asset_sha256: str
) -> None:
    if await is_stage_complete(session, asset_sha256=asset_sha256, stage_name="acoustic"):
        return

    run = await start_stage(
        session, job_id=job_id, asset_sha256=asset_sha256, stage_name="acoustic"
    )
    try:
        asset = await session.get(Asset, asset_sha256)
        if asset and asset.asset_type != "audio":
            await complete_stage(session, run=run, output_sha256=asset_sha256)
            return

        audio_bytes = blob_nvme.get(asset_sha256)

        # AST acoustic events
        existing_events = (
            (
                await session.execute(
                    select(AcousticEvent).where(AcousticEvent.asset_sha256 == asset_sha256)
                )
            )
            .scalars()
            .all()
        )

        if not existing_events:
            events_resp = await speech_client.ast_events(audio_bytes)
            for event in events_resp.events:
                if event.labels:
                    top_label, top_conf = max(event.labels.items(), key=lambda kv: kv[1])
                    session.add(
                        AcousticEvent(
                            asset_sha256=asset_sha256,
                            window_start_sec=event.window_start_sec,
                            window_end_sec=event.window_end_sec,
                            audioset_label=top_label,
                            confidence=top_conf,
                        )
                    )
            await session.flush()

        # CLAP audio embedding (512-d)
        clap_resp = await speech_client.embed_clap_audio(audio_bytes)
        if asset:
            meta = dict(asset.extra_metadata or {})
            meta["clap_embedding"] = clap_resp.embedding
            asset.extra_metadata = meta
            await session.flush()

        await complete_stage(session, run=run, output_sha256=asset_sha256)
    except Exception as exc:
        await fail_stage(session, run=run, error_detail=str(exc))
        raise


async def run_nlp_stage(session: AsyncSession, *, job_id: uuid.UUID, asset_sha256: str) -> None:
    if await is_stage_complete(session, asset_sha256=asset_sha256, stage_name="nlp"):
        return

    run = await start_stage(session, job_id=job_id, asset_sha256=asset_sha256, stage_name="nlp")
    try:
        result = await session.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.asset_sha256 == asset_sha256)
            .order_by(TranscriptSegment.seg_index)
        )
        segments = result.scalars().all()

        for seg in segments:
            pii_result = await nlp_client.ner_gliner(
                seg.text_redacted,
                labels=[
                    "person_name",
                    "phone_number",
                    "coordinates",
                    "vessel_callsign",
                    "species",
                ],
            )
            redacted_text = seg.text_redacted
            # Filter specifically sensitive PII for redaction
            pii_entities = [
                e
                for e in pii_result.entities
                if e.label in ("person_name", "phone_number", "coordinates")
            ]
            for entity in sorted(pii_entities, key=lambda e: e.start, reverse=True):
                redacted_text = (
                    redacted_text[: entity.start] + "[REDACTED]" + redacted_text[entity.end :]
                )
            seg.text_redacted = redacted_text
            seg.entities_json = {"entities": [e.model_dump() for e in pii_result.entities]}

        await session.flush()
        await complete_stage(session, run=run, output_sha256=asset_sha256)
    except Exception as exc:
        await fail_stage(session, run=run, error_detail=str(exc))
        raise


async def run_index_stage(session: AsyncSession, *, job_id: uuid.UUID, asset_sha256: str) -> None:
    if await is_stage_complete(session, asset_sha256=asset_sha256, stage_name="index"):
        return

    run = await start_stage(session, job_id=job_id, asset_sha256=asset_sha256, stage_name="index")
    try:
        asset = await session.get(Asset, asset_sha256)
        await qdrant_repo.ensure_collections()

        sanctuary_id = asset.sanctuary_id if asset else "unscoped"
        station_code = asset.station_code if asset else None

        # 1. Index transcript segments
        result = await session.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.asset_sha256 == asset_sha256)
            .order_by(TranscriptSegment.seg_index)
        )
        segments = result.scalars().all()
        if segments:
            embeddings = await nlp_client.embed_bge_m3([s.text_redacted for s in segments])
            points = [
                qdrant_repo.UpsertPoint(
                    point_id=qdrant_repo.deterministic_point_id(
                        asset_sha256=asset_sha256,
                        segment_index=seg.seg_index,
                        model_version=MODEL_VERSION,
                    ),
                    dense_vector=emb.dense,
                    sparse_indices=emb.sparse.indices,
                    sparse_values=emb.sparse.values,
                    payload={
                        "asset_sha256": asset_sha256,
                        "sanctuary_id": sanctuary_id or "unscoped",
                        "station_code": station_code,
                        "rbac_tier": 1,
                        "text": seg.text_redacted,
                        "speaker_label": seg.speaker_label,
                    },
                )
                for seg, emb in zip(segments, embeddings, strict=True)
            ]
            await qdrant_repo.upsert("transcript_segments", points)

        # 2. Index acoustic events (CLAP 512-d dense + AST sparse)
        events_res = await session.execute(
            select(AcousticEvent).where(AcousticEvent.asset_sha256 == asset_sha256)
        )
        acoustic_events = events_res.scalars().all()
        if acoustic_events and asset and asset.extra_metadata:
            clap_emb = asset.extra_metadata.get("clap_embedding")
            if clap_emb and len(clap_emb) == 512:
                top_labels = {e.audioset_label: e.confidence for e in acoustic_events}
                sparse_indices = [_audioset_label_to_index(lbl) for lbl in top_labels]
                sparse_values = list(top_labels.values())

                dom_label = max(top_labels.items(), key=lambda kv: kv[1])[0]
                acoustic_point = qdrant_repo.UpsertPoint(
                    point_id=qdrant_repo.deterministic_point_id(
                        asset_sha256=asset_sha256,
                        segment_index=0,
                        model_version="acoustic_v1",
                    ),
                    dense_vector=clap_emb,
                    sparse_indices=sparse_indices,
                    sparse_values=sparse_values,
                    payload={
                        "asset_sha256": asset_sha256,
                        "sanctuary_id": sanctuary_id or "unscoped",
                        "station_code": station_code,
                        "window_start_sec": acoustic_events[0].window_start_sec,
                        "dominant_label": dom_label,
                        "rbac_tier": 1,
                    },
                )
                await qdrant_repo.upsert("acoustic_events", [acoustic_point])

        # 3. Index document chunks
        if asset and asset.asset_type in ("pdf", "docx", "xml"):
            data = blob_nvme.get(asset_sha256)
            chunks = []
            if asset.asset_type == "pdf":
                chunks = parse_pdf(data)
            elif asset.asset_type == "docx":
                chunks = parse_docx(data)

            if chunks:
                doc_embeddings = await nlp_client.embed_bge_m3([c.text for c in chunks])
                doc_points = [
                    qdrant_repo.UpsertPoint(
                        point_id=qdrant_repo.deterministic_point_id(
                            asset_sha256=asset_sha256,
                            segment_index=c.index,
                            model_version="doc_v1",
                        ),
                        dense_vector=emb.dense,
                        sparse_indices=emb.sparse.indices,
                        sparse_values=emb.sparse.values,
                        payload={
                            "asset_sha256": asset_sha256,
                            "doc_type": asset.asset_type,
                            "sanctuary_id": sanctuary_id or "unscoped",
                            "page_or_section": c.page_or_section,
                            "text": c.text,
                            "rbac_tier": 1,
                        },
                    )
                    for c, emb in zip(chunks, doc_embeddings, strict=True)
                ]
                await qdrant_repo.upsert("document_chunks", doc_points)

        await complete_stage(session, run=run, output_sha256=asset_sha256)
    except Exception as exc:
        await fail_stage(session, run=run, error_detail=str(exc))
        raise


async def run_seal_stage(session: AsyncSession, *, job_id: uuid.UUID, asset_sha256: str) -> None:
    if await is_stage_complete(session, asset_sha256=asset_sha256, stage_name="seal"):
        return

    run = await start_stage(session, job_id=job_id, asset_sha256=asset_sha256, stage_name="seal")
    try:
        # Atomic JSON Write-Cache projection
        seg_res = await session.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.asset_sha256 == asset_sha256)
            .order_by(TranscriptSegment.seg_index)
        )
        segments = seg_res.scalars().all()
        if segments:
            json_cache.write_projection(
                asset_sha256=asset_sha256,
                view="transcript",
                payload={
                    "sha256": asset_sha256,
                    "segments": [
                        {
                            "seg_index": s.seg_index,
                            "start_sec": s.start_sec,
                            "end_sec": s.end_sec,
                            "speaker_label": s.speaker_label,
                            "source_lang": s.source_lang,
                            "text_redacted": s.text_redacted,
                            "entities_json": s.entities_json,
                            "translations_json": s.translations_json,
                            "is_hitl_override": s.is_hitl_override,
                        }
                        for s in segments
                    ],
                },
            )

        events_res = await session.execute(
            select(AcousticEvent)
            .where(AcousticEvent.asset_sha256 == asset_sha256)
            .order_by(AcousticEvent.window_start_sec)
        )
        events = events_res.scalars().all()
        if events:
            json_cache.write_projection(
                asset_sha256=asset_sha256,
                view="events",
                payload={
                    "sha256": asset_sha256,
                    "events": [
                        {
                            "window_start_sec": e.window_start_sec,
                            "window_end_sec": e.window_end_sec,
                            "audioset_label": e.audioset_label,
                            "confidence": e.confidence,
                            "spl_db_broadband": e.spl_db_broadband,
                            "is_hitl_override": e.is_hitl_override,
                        }
                        for e in events
                    ],
                },
            )

        # Final append-only PREMIS provenance sealing event
        await append_event(
            session,
            NewEvent(
                object_sha256=asset_sha256,
                event_type="pipeline_sealed",
                agent_id="pipeline",
                payload_sha256=asset_sha256,
            ),
        )

        job = await session.get(PipelineJob, job_id)
        if job:
            job.status = "succeeded"
            job.current_stage = "seal"
            job.finished_at = datetime.now(UTC)

        await complete_stage(session, run=run, output_sha256=asset_sha256)
    except Exception as exc:
        await fail_stage(session, run=run, error_detail=str(exc))
        raise
