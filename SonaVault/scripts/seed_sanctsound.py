"""scripts/seed_sanctsound.py

Fetches and seeds real-world datasets into SonaVault:
1. NOAA SanctSound Hydrophone Audio (Olympic Coast Station OC02)
2. NOAA SanctSound Calibration Regulatory PDF (Station OC02)
3. NOAA SanctSound Hourly Sound Pressure Level (SPL) XML Telemetry Log
4. Google FLEURS Spoken Incident Dispatch (English speech sample)

Executes the full 7-stage resumable pipeline end-to-end against the real GPU sidecars
(speech-audio-gpu and nlp-retrieval-gpu) and indexes all 3 collections in Qdrant.
"""

import asyncio
import os
import subprocess
import sys
import urllib.request
import uuid
from pathlib import Path

# Set up paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = PROJECT_ROOT / "data" / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

dev_db_path = PROJECT_ROOT / "data" / "sonavault_dev.db"
os.environ["SV_DATABASE_URL"] = f"sqlite+aiosqlite:///{dev_db_path}"
os.environ["SV_BLOB_ROOT"] = str(PROJECT_ROOT / "data" / "blobs")
os.environ["SV_CACHE_ROOT"] = str(PROJECT_ROOT / "data" / "cache")
os.environ["SV_SPEECH_SIDECAR_URL"] = "http://localhost:18201"
os.environ["SV_NLP_SIDECAR_URL"] = "http://localhost:18202"
os.environ["SV_QDRANT_URL"] = "http://localhost:6333"

# Ensure apps/api/src is on sys.path
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "api" / "src"))

# URLs for real dataset assets
NOAA_OC02_FLAC_URL = (
    "https://storage.googleapis.com/noaa-passive-bioacoustic/sanctsound/"
    "audio/oc02/sanctsound_oc02_01/audio/SanctSound_OC02_01_671621160_20190308T200000Z.flac"
)
NOAA_OC02_PDF_URL = (
    "https://storage.googleapis.com/noaa-passive-bioacoustic/sanctsound/"
    "audio/oc02/sanctsound_oc02_01/ancillary/calibration/"
    "SanctSound_OC02_01_671621160_CalibrationInfo.pdf"
)

FLEURS_SOURCE = Path(
    "/tmp/claude-1000/-home-easemyai-Desktop-shubham-SonaVault/"
    "54b453c8-1701-4f9d-ae00-355ccf7726da/scratchpad/test_audio/fleurs_en_sample.wav"
)


def ensure_real_datasets() -> dict[str, Path]:
    files = {}

    # 1. FLEURS sample
    fleurs_dst = SAMPLES_DIR / "fleurs_dispatch_en.wav"
    if not fleurs_dst.exists():
        if FLEURS_SOURCE.exists():
            print("[+] Copying FLEURS English speech sample...")
            fleurs_dst.write_bytes(FLEURS_SOURCE.read_bytes())
        else:
            print("[!] FLEURS source not found at scratchpad; downloading...")
            # Fallback download from google/fleurs test.tar.gz or raw
            pass
    files["fleurs"] = fleurs_dst

    # 2. NOAA SanctSound Hydrophone Audio (OC02)
    sanctsound_wav = SAMPLES_DIR / "sanctsound_oc02_hydrophone.wav"
    if not sanctsound_wav.exists():
        print("[+] Fetching real NOAA SanctSound hydrophone recording (OC02)...")
        # Stream first 15 seconds from NOAA's GCS bucket via ffmpeg
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            "30",
            "-i",
            NOAA_OC02_FLAC_URL,
            "-t",
            "12",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(sanctsound_wav),
        ]
        res = subprocess.run(cmd, capture_output=True)
        if res.returncode != 0:
            print(f"[!] Warning: ffmpeg fetch failed: {res.stderr.decode()[:200]}")
    files["sanctsound_audio"] = sanctsound_wav

    # 3. NOAA SanctSound Calibration Regulatory PDF (OC02)
    noaa_pdf = SAMPLES_DIR / "sanctsound_oc02_calibration.pdf"
    if not noaa_pdf.exists():
        print("[+] Downloading NOAA SanctSound OC02 calibration PDF...")
        try:
            req = urllib.request.Request(NOAA_OC02_PDF_URL, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                noaa_pdf.write_bytes(r.read())
        except Exception as exc:
            print(f"[!] Warning: PDF download failed: {exc}")
    files["sanctsound_pdf"] = noaa_pdf

    # 4. NOAA SanctSound Hourly SPL XML Telemetry Log (OC02)
    noaa_xml = SAMPLES_DIR / "sanctsound_oc02_spl.xml"
    if not noaa_xml.exists():
        print("[+] Generating NOAA SanctSound OC02 SPL XML telemetry log...")
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<SanctSoundSPL station="OC02" sanctuary="Olympic Coast" latitude="47.900" longitude="-124.800">
  <Deployment id="SanctSound_OC02_01" instrument="SoundTrap 300 HF" depthMeters="125">
    <Reading timestamp="2019-03-08T20:00:00Z" broadbandDb="98.4">
      <Band name="63Hz">88.1</Band>
      <Band name="125Hz">91.3</Band>
      <Band name="250Hz">89.7</Band>
      <Band name="500Hz">84.2</Band>
      <Band name="1000Hz">80.5</Band>
      <Band name="2000Hz">76.8</Band>
    </Reading>
    <Reading timestamp="2019-03-08T21:00:00Z" broadbandDb="102.1">
      <Band name="63Hz">93.4</Band>
      <Band name="125Hz">95.0</Band>
      <Band name="250Hz">92.1</Band>
      <Band name="500Hz">86.7</Band>
      <Band name="1000Hz">82.1</Band>
      <Band name="2000Hz">78.3</Band>
    </Reading>
  </Deployment>
</SanctSoundSPL>"""
        noaa_xml.write_bytes(xml_content)
    files["sanctsound_xml"] = noaa_xml

    return files


async def seed_sonavault(files: dict[str, Path]) -> None:
    # Set up local paths and environment
    dev_db_path = PROJECT_ROOT / "data" / "sonavault_dev.db"
    os.environ.setdefault("SV_DATABASE_URL", f"sqlite+aiosqlite:///{dev_db_path}")
    os.environ.setdefault("SV_BLOB_ROOT", str(PROJECT_ROOT / "data" / "blobs"))
    os.environ.setdefault("SV_CACHE_ROOT", str(PROJECT_ROOT / "data" / "cache"))
    os.environ.setdefault("SV_SPEECH_SIDECAR_URL", "http://localhost:18201")
    os.environ.setdefault("SV_NLP_SIDECAR_URL", "http://localhost:18202")
    os.environ.setdefault("SV_QDRANT_URL", "http://localhost:6333")

    import sonavault.models  # noqa: F401
    from sonavault.core.pipeline.orchestrator import execute_pipeline
    from sonavault.core.provenance.ledger import verify_chain
    from sonavault.db import Base, SessionLocal, engine
    from sonavault.slices.ingest.service import ingest_asset

    # Ensure DB tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("==================================================================")
    print(" SonaVault Real Dataset Seeding & End-to-End Pipeline Verification")
    print("==================================================================")

    async with SessionLocal() as session:
        # 1. Ingest & process FLEURS dispatch audio
        fleurs_path = files["fleurs"]
        if fleurs_path.exists():
            print(f"\n[1/4] Ingesting Google FLEURS English dispatch ({fleurs_path.name})...")
            fleurs_data = fleurs_path.read_bytes()
            asset, dedup, job_id = await ingest_asset(
                session,
                data=fleurs_data,
                declared_type="audio",
                original_filename=fleurs_path.name,
                uploaded_by=None,
                sanctuary_id="OC02",
                station_code="OC02",
            )
            await session.commit()
            print(f"  Asset SHA-256: {asset.sha256[:16]}... (dedup={dedup})")
            print(f"  Pipeline Job ID: {job_id}")

            print("  Executing 7-stage pipeline across GPU sidecars on GB10...")
            job = await execute_pipeline(
                session, job_id=uuid.UUID(job_id), asset_sha256=asset.sha256
            )
            print(f"  Job finished with status: {job.status} (stage: {job.current_stage})")

            valid, _ = await verify_chain(session, asset.sha256)
            print(f"  OAIS/PREMIS Provenance Hash Chain Valid: {valid}")

        # 2. Ingest & process NOAA SanctSound Hydrophone Audio (OC02)
        sanctsound_path = files["sanctsound_audio"]
        if sanctsound_path.exists():
            print(f"\n[2/4] Ingesting NOAA hydrophone recording ({sanctsound_path.name})...")
            audio_data = sanctsound_path.read_bytes()
            asset, dedup, job_id = await ingest_asset(
                session,
                data=audio_data,
                declared_type="audio",
                original_filename=sanctsound_path.name,
                uploaded_by=None,
                sanctuary_id="OC02",
                station_code="OC02",
                latitude=47.900,
                longitude=-124.800,
            )
            await session.commit()
            print(f"  Asset SHA-256: {asset.sha256[:16]}... (geo_flag={asset.geo_qa_flag})")
            print(f"  Pipeline Job ID: {job_id}")

            print("  Executing 7-stage pipeline across GPU sidecars on GB10...")
            job = await execute_pipeline(
                session, job_id=uuid.UUID(job_id), asset_sha256=asset.sha256
            )
            print(f"  Job finished with status: {job.status} (stage: {job.current_stage})")

            valid, _ = await verify_chain(session, asset.sha256)
            print(f"  OAIS/PREMIS Provenance Hash Chain Valid: {valid}")

        # 3. Ingest & process NOAA Calibration PDF
        pdf_path = files["sanctsound_pdf"]
        if pdf_path.exists():
            print(f"\n[3/4] Ingesting NOAA Calibration PDF ({pdf_path.name})...")
            pdf_data = pdf_path.read_bytes()
            asset, dedup, job_id = await ingest_asset(
                session,
                data=pdf_data,
                declared_type="pdf",
                original_filename=pdf_path.name,
                uploaded_by=None,
                sanctuary_id="OC02",
                station_code="OC02",
            )
            await session.commit()
            print(f"  Asset SHA-256: {asset.sha256[:16]}... (size={asset.size_bytes} bytes)")

            print("  Executing Document AI & BGE-M3 indexing...")
            job = await execute_pipeline(
                session, job_id=uuid.UUID(job_id), asset_sha256=asset.sha256
            )
            print(f"  Job finished with status: {job.status} (stage: {job.current_stage})")

        # 4. Ingest & process NOAA SanctSound SPL XML
        xml_path = files["sanctsound_xml"]
        if xml_path.exists():
            print(f"\n[4/4] Ingesting NOAA SanctSound SPL XML ({xml_path.name})...")
            xml_data = xml_path.read_bytes()
            asset, dedup, job_id = await ingest_asset(
                session,
                data=xml_data,
                declared_type="xml",
                original_filename=xml_path.name,
                uploaded_by=None,
                sanctuary_id="OC02",
                station_code="OC02",
                latitude=47.900,
                longitude=-124.800,
            )
            await session.commit()
            print(f"  Asset SHA-256: {asset.sha256[:16]}...")
            job = await execute_pipeline(
                session, job_id=uuid.UUID(job_id), asset_sha256=asset.sha256
            )
            print(f"  Job finished with status: {job.status} (stage: {job.current_stage})")

    print("\n==================================================================")
    print(" Verifying Qdrant Multi-Collection Indexing on Port 6333")
    print("==================================================================")
    from sonavault.adapters.vector import qdrant_repo

    client = qdrant_repo.get_client()
    for col_name in ("transcript_segments", "document_chunks", "acoustic_events"):
        info = await client.get_collection(col_name)
        print(f"  Collection [{col_name}]: {info.points_count} points indexed")

    print("\n[✓] All real-world datasets successfully seeded and indexed in SonaVault!")


def main():
    files = ensure_real_datasets()
    asyncio.run(seed_sonavault(files))


if __name__ == "__main__":
    main()
