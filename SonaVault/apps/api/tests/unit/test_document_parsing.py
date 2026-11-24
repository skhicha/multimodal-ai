import pymupdf as fitz
from docx import Document as DocxDocument

from sonavault.slices.documents.parsing import parse_docx, parse_pdf, parse_sanctsound_spl_xml


def _make_pdf_bytes(pages: list[str]) -> bytes:
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_parse_pdf_extracts_text_per_page():
    data = _make_pdf_bytes(["Vessel-routing notice for OC02", "Impact assessment summary"])
    chunks = parse_pdf(data)
    assert len(chunks) == 2
    assert "OC02" in chunks[0].text
    assert chunks[0].page_or_section == 0
    assert chunks[1].page_or_section == 1


def test_parse_pdf_skips_blank_pages():
    data = _make_pdf_bytes(["Field inspection log entry", ""])
    chunks = parse_pdf(data)
    assert len(chunks) == 1


def _make_docx_bytes() -> bytes:
    import io

    doc = DocxDocument()
    doc.add_paragraph("Sanctuary observer field dispatch")
    doc.add_paragraph("Vessel callsign WDF1234 reported in zone B")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Species"
    table.rows[0].cells[1].text = "Humpback whale"
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_parse_docx_extracts_paragraphs_and_tables():
    chunks = parse_docx(_make_docx_bytes())
    texts = [c.text for c in chunks]
    assert any("Sanctuary observer field dispatch" in t for t in texts)
    assert any("WDF1234" in t for t in texts)
    assert any("Humpback whale" in t for t in texts)


SANCTSOUND_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<SanctSoundSPL station="OC02">
  <Reading timestamp="2024-01-01T00:00:00Z" broadbandDb="98.4">
    <Band name="63Hz">88.1</Band>
    <Band name="125Hz">91.3</Band>
  </Reading>
  <Reading timestamp="2024-01-01T01:00:00Z" broadbandDb="101.2">
    <Band name="63Hz">90.0</Band>
  </Reading>
</SanctSoundSPL>
"""


def test_parse_sanctsound_spl_xml():
    readings = parse_sanctsound_spl_xml(SANCTSOUND_XML)
    assert len(readings) == 2
    assert readings[0].station_code == "OC02"
    assert readings[0].broadband_db == 98.4
    assert readings[0].bands["63Hz"] == 88.1
    assert readings[1].bands["63Hz"] == 90.0
