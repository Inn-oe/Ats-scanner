import io
from pathlib import Path

import pytest

from ats import analyze, extract_text
from ats.analyzer import find_skills

SAMPLES = Path(__file__).parent.parent / "samples"
CV = (SAMPLES / "sample_cv.txt").read_text()
JOB = (SAMPLES / "job_data_analyst_graduate.txt").read_text()


def test_sample_produces_sensible_score():
    r = analyze(CV, JOB)
    assert 0 <= r.score <= 100
    names = {s.name for s in r.matched_skills}
    assert {"Python", "SQL", "Excel", "Pandas"} <= names
    missing = {s.name for s in r.missing_skills}
    assert "Power BI" in missing
    assert r.suggestions


def test_either_or_skill_not_counted_as_required():
    r = analyze(CV, JOB)
    rskill = next(s for s in r.skills if s.name == "R")
    assert rskill.importance == "alternative"


def test_desirable_detection():
    r = analyze(CV, JOB)
    aws = next(s for s in r.skills if s.name == "AWS")
    assert aws.importance == "desirable"


def test_r_language_is_case_sensitive():
    assert "R" in find_skills("Skills: Python, R, SQL")
    assert "R" not in find_skills("I worked in r&d and read a lot")
    assert "R" not in find_skills("Worked at R&D department")


def test_tailored_cv_scores_higher():
    tailored = CV + (
        "\nBuilt a Power BI dashboard on Azure data warehouse; presented insights to non-technical stakeholders "
        "with strong communication, problem solving and attention to detail. Curious and eager to learn. "
        "Used R for statistical analysis. Automated reports, interpreted large datasets as a data analyst."
    )
    assert analyze(tailored, JOB).score > analyze(CV, JOB).score


def test_plain_list_of_qualities_works():
    r = analyze(CV, "Python, SQL, Tableau, teamwork, leadership")
    assert {s.name for s in r.matched_skills} >= {"Python", "SQL", "Tableau", "Teamwork"}
    assert "Leadership" in {s.name for s in r.missing_skills}


def test_empty_inputs_raise():
    with pytest.raises(ValueError):
        analyze("", JOB)
    with pytest.raises(ValueError):
        analyze(CV, "  ")


def test_docx_parsing():
    import docx

    d = docx.Document()
    d.add_paragraph("Skills: Python and SQL")
    t = d.add_table(rows=1, cols=2)
    t.rows[0].cells[0].text = "Power BI"
    buf = io.BytesIO()
    d.save(buf)
    text = extract_text(buf.getvalue(), "cv.docx")
    assert "Python" in text and "Power BI" in text


def test_unsupported_file():
    from ats.parser import UnsupportedFileError

    with pytest.raises(UnsupportedFileError):
        extract_text(b"x", "cv.doc")
