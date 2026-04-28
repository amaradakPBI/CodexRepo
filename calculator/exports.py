from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from .storage import HistoryEntry


def history_to_text(entries: list[HistoryEntry]) -> str:
    lines = []
    for entry in entries:
        lines.append(f"[{entry.timestamp}] {entry.expression} = {entry.result}")
        if entry.formula:
            lines.append(f"  {entry.formula}")
    return "\n".join(lines)


def history_to_json(entries: list[HistoryEntry]) -> str:
    return json.dumps([entry.__dict__ for entry in entries], indent=2)


def history_to_pdf(entries: list[HistoryEntry], output_path: Path) -> None:
    pdf = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter
    y = height - 40
    pdf.setTitle("Calculator History")
    pdf.setFont("Helvetica", 11)
    for line in history_to_text(entries).splitlines() or ["No history"]:
        if y < 40:
            pdf.showPage()
            pdf.setFont("Helvetica", 11)
            y = height - 40
        pdf.drawString(40, y, line[:100])
        y -= 16
    pdf.save()
