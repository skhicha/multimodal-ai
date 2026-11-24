"""CPU-only Document AI: layout-aware PDF text extraction (PyMuPDF), DOCX
paragraph/table extraction (python-docx), and NOAA SanctSound hourly SPL XML
parsing (lxml). Deliberately non-visual: no page rasterization, no OCR — PDFs
are parsed for their native text layer only, keeping the whole pipeline
image-free per SonaVault's domain constraint.
"""

from dataclasses import dataclass, field

import pymupdf as fitz  # PyMuPDF (modern import name)
from docx import Document as DocxDocument
from lxml import etree


@dataclass
class DocumentChunk:
    index: int
    text: str
    page_or_section: int


def parse_pdf(data: bytes) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for page_index, page in enumerate(doc):
            text = page.get_text("text").strip()
            if text:
                chunks.append(
                    DocumentChunk(index=len(chunks), text=text, page_or_section=page_index)
                )
    return chunks


def parse_docx(data: bytes) -> list[DocumentChunk]:
    import io

    doc = DocxDocument(io.BytesIO(data))
    chunks: list[DocumentChunk] = []
    section = 0

    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            chunks.append(DocumentChunk(index=len(chunks), text=text, page_or_section=section))

    for table_index, table in enumerate(doc.tables):
        rows_text = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                rows_text.append(" | ".join(cells))
        if rows_text:
            chunks.append(
                DocumentChunk(
                    index=len(chunks),
                    text="\n".join(rows_text),
                    page_or_section=section + table_index,
                )
            )

    return chunks


@dataclass
class SplReading:
    timestamp: str
    station_code: str
    broadband_db: float
    bands: dict[str, float] = field(default_factory=dict)


def parse_sanctsound_spl_xml(data: bytes) -> list[SplReading]:
    """Parses NOAA SanctSound-style hourly SPL XML logs:

    <SanctSoundSPL station="OC02">
      <Reading timestamp="2024-01-01T00:00:00Z" broadbandDb="98.4">
        <Band name="63Hz">88.1</Band>
        <Band name="125Hz">91.3</Band>
      </Reading>
    </SanctSoundSPL>
    """
    root = etree.fromstring(data)
    station_code = root.get("station", "")
    readings: list[SplReading] = []

    for reading_el in root.findall("Reading"):
        bands = {
            band_el.get("name", f"band_{i}"): float(band_el.text)
            for i, band_el in enumerate(reading_el.findall("Band"))
            if band_el.text is not None
        }
        readings.append(
            SplReading(
                timestamp=reading_el.get("timestamp", ""),
                station_code=station_code,
                broadband_db=float(reading_el.get("broadbandDb", "nan")),
                bands=bands,
            )
        )
    return readings
