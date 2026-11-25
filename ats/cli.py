"""Command line interface.

Usage:
    python -m ats.cli path/to/cv.pdf path/to/job.txt
    python -m ats.cli cv.docx --job "paste the advert or the qualities you want here"
    python -m ats.cli cv.pdf job.txt --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analyzer import analyze
from .parser import extract_text_from_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Score a CV against a job advert, the way an ATS would.")
    p.add_argument("cv", help="CV file (.pdf, .docx or .txt)")
    p.add_argument("job_file", nargs="?", help="Text file with the job advert or the qualities you need")
    p.add_argument("--job", help="Job advert text (instead of a file)")
    p.add_argument("--json", action="store_true", help="Print the full result as JSON")
    args = p.parse_args(argv)

    if args.job:
        job_text = args.job
    elif args.job_file:
        job_text = Path(args.job_file).read_text(encoding="utf-8", errors="ignore")
    else:
        print("Paste the job advert, then press Ctrl-D (Ctrl-Z then Enter on Windows):", file=sys.stderr)
        job_text = sys.stdin.read()

    cv_text = extract_text_from_path(args.cv)
    result = analyze(cv_text, job_text)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    print(f"\nATS match score: {result.score}/100")
    print(result.verdict)
    print("\nBreakdown:")
    for k, v in result.breakdown.items():
        print(f"  {k:<24} {v:>3}%")

    print("\nSkills found:")
    for s in result.matched_skills:
        print(f"  ✔ {s.name} ({s.importance}, {s.category})")
    print("\nSkills missing:")
    for s in result.missing_skills:
        print(f"  ✘ {s.name} ({s.importance}, {s.category})")
    print("\nKeywords found:   " + (", ".join(result.keywords_found) or "-"))
    print("Keywords missing: " + (", ".join(result.keywords_missing) or "-"))

    print("\nCV checks:")
    for k, ok in result.checks.items():
        print(f"  {'✔' if ok else '✘'} {k}")

    print("\nSuggestions:")
    for i, s in enumerate(result.suggestions, 1):
        print(f"  {i}. [{s.priority.upper()}] {s.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
