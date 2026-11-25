"""Read text out of CV files (PDF, DOCX, TXT/MD)."""

from __future__ import annotations

import io
import re
from pathlib import Path


class UnsupportedFileError(ValueError):
    pass


def extract_text(data: bytes, filename: str) -> str:
    """Return the plain text of a CV given its raw bytes and file name."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        text = _pdf_text(data)
    elif suffix == ".docx":
        text = _docx_text(data)
    elif suffix in {".txt", ".md", ".text", ""}:
        text = data.decode("utf-8", errors="ignore")
    elif suffix == ".doc":
        raise UnsupportedFileError("Old .doc files are not supported. Save the CV as .docx or PDF and try again.")
    else:
        raise UnsupportedFileError(f"Unsupported file type '{suffix}'. Use PDF, DOCX or TXT.")
    return clean_text(text)


def extract_text_from_path(path: str | Path) -> str:
    path = Path(path)
    return extract_text(path.read_bytes(), path.name)


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _docx_text(data: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(data))
    parts = [p.text for p in document.paragraphs]
    # Many CV templates put content in tables; ATS systems read those too.
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def clean_text(text: str) -> str:
    text = text.replace(" ", " ").replace("•", "\n• ").replace("", "\n• ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()
