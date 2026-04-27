from io import BytesIO

import pytest
from reportlab.pdfgen import canvas

from chatbot.attachments import build_attachment_context, parse_uploads


class DummyUpload:
    def __init__(self, name: str, raw: bytes):
        self.name = name
        self._raw = raw

    def getvalue(self) -> bytes:
        return self._raw


def make_pdf_bytes(text: str) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 720, text)
    pdf.save()
    return buffer.getvalue()


def test_parse_text_upload():
    uploads = [DummyUpload("notes.txt", b"hello world")]
    parsed = parse_uploads(uploads, max_upload_mb=1)
    assert parsed[0].meta.chars == 11
    assert "hello world" in build_attachment_context(parsed)


def test_rejects_bad_extension():
    with pytest.raises(ValueError):
        parse_uploads([DummyUpload("notes.exe", b"nope")], max_upload_mb=1)


def test_parse_pdf_upload():
    uploads = [DummyUpload("notes.pdf", make_pdf_bytes("sample text"))]
    parsed = parse_uploads(uploads, max_upload_mb=1)
    assert parsed[0].meta.mime_type == "application/pdf"
