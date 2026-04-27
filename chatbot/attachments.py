from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader

from chatbot.models import AttachmentMeta


ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}


@dataclass
class AttachmentPayload:
    meta: AttachmentMeta
    content: str


def _read_text_bytes(raw: bytes) -> str:
    return raw.decode("utf-8", errors="ignore")


def extract_pdf_text(raw: bytes) -> str:
    reader = PdfReader(BytesIO(raw))
    chunks: list[str] = []
    for page in reader.pages:
        chunks.append(page.extract_text() or "")
    return "\n".join(chunks).strip()


def parse_uploads(files: Iterable, max_upload_mb: int) -> list[AttachmentPayload]:
    parsed: list[AttachmentPayload] = []
    max_bytes = max_upload_mb * 1024 * 1024
    for index, uploaded in enumerate(files):
        if index >= 3:
            break
        suffix = Path(uploaded.name).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {uploaded.name}")
        raw = uploaded.getvalue()
        if len(raw) > max_bytes:
            raise ValueError(f"File too large: {uploaded.name}")
        if suffix == ".pdf":
            content = extract_pdf_text(raw)
            mime_type = "application/pdf"
        else:
            content = _read_text_bytes(raw)
            mime_type = "text/plain"
        parsed.append(
            AttachmentPayload(
                meta=AttachmentMeta(
                    name=uploaded.name,
                    mime_type=mime_type,
                    size_bytes=len(raw),
                    chars=len(content),
                ),
                content=content,
            )
        )
    return parsed


def build_attachment_context(attachments: list[AttachmentPayload]) -> str:
    if not attachments:
        return ""
    blocks = []
    for attachment in attachments:
        blocks.append(
            f"[Attachment: {attachment.meta.name}]\n{attachment.content.strip()}\n[/Attachment]"
        )
    return "\n\n".join(blocks)
