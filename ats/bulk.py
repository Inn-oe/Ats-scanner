"""Bulk import: many CV files, or ZIP archives full of them."""

from __future__ import annotations

import hashlib
import io
import zipfile
from collections.abc import Callable, Iterable
from pathlib import PurePosixPath

from .parser import extract_text
from .screening import CandidateFacts, extract_facts

SUPPORTED = {".pdf", ".docx", ".txt", ".md"}
MAX_FILES = 1000
MAX_UNZIPPED_BYTES = 400 * 1024 * 1024


def expand_uploads(files: Iterable[tuple[str, bytes]]) -> tuple[list[tuple[str, bytes]], list[str]]:
    """Turn uploads into a flat list of (name, bytes), opening ZIPs. Returns (files, problems)."""
    out: list[tuple[str, bytes]] = []
    problems: list[str] = []
    budget = MAX_UNZIPPED_BYTES
    for name, data in files:
        if not name.lower().endswith(".zip"):
            out.append((name, data))
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for info in zf.infolist():
                    base = PurePosixPath(info.filename)
                    if info.is_dir() or "__MACOSX" in base.parts or base.name.startswith("."):
                        continue
                    if base.suffix.lower() not in SUPPORTED:
                        continue
                    if info.file_size > budget:
                        problems.append(f"{name}/{base.name}: skipped, archive is too large to unpack safely")
                        continue
                    budget -= info.file_size
                    out.append((f"{name}/{base.name}", zf.read(info)))
        except zipfile.BadZipFile:
            problems.append(f"{name}: not a valid ZIP file")
    if len(out) > MAX_FILES:
        problems.append(f"Only the first {MAX_FILES} CVs were read ({len(out)} found).")
        out = out[:MAX_FILES]
    return out, problems


def load_candidates(
    files: Iterable[tuple[str, bytes]],
    progress: Callable[[int, int, str], None] | None = None,
) -> tuple[list[CandidateFacts], list[str]]:
    """Read every CV. Unreadable, empty and duplicate files are reported, not fatal."""
    flat, problems = expand_uploads(files)
    candidates: list[CandidateFacts] = []
    seen: set[str] = set()
    for i, (name, data) in enumerate(flat, 1):
        if progress:
            progress(i, len(flat), name)
        digest = hashlib.sha1(data).hexdigest()
        if digest in seen:
            problems.append(f"{name}: skipped, identical to a file already imported")
            continue
        seen.add(digest)
        try:
            text = extract_text(data, name.split("/")[-1])
        except Exception as e:  # noqa: BLE001 - report and carry on
            problems.append(f"{name}: could not be read ({e})")
            continue
        if len(text.strip()) < 50:
            problems.append(f"{name}: no readable text (scanned or image-only PDF?)")
            continue
        candidates.append(extract_facts(name, text))
    return candidates, problems
