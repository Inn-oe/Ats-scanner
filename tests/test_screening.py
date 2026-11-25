import datetime as dt
import io
import zipfile

from ats.bulk import expand_uploads, load_candidates
from ats.screening import (
    Requirements, evaluate, extract_age, extract_facts, rank, years_of_experience,
)

TODAY = dt.date(2026, 11, 25)

CV_A = """Tendai Moyo
tendai@example.com | +263 77 111 2222
Date of Birth: 12/05/1996

Education
National Diploma in Accounting, Harare Polytechnic, 2015 - 2017

Work Experience
Accounts Clerk, ABC Ltd, Jan 2018 - Dec 2021
Senior Accountant, XYZ Pvt, Jan 2022 - Present
Held a clean class 4 driver's licence. Skilled in Excel and Pastel.
"""

CV_B = """Rudo Ncube
Age: 24
Education
BSc (Hons) Data Science, 2020 - 2024
Experience
Data Intern, Jun 2025 - Aug 2025
Python, SQL
"""


def facts(text, name="cv.txt"):
    return extract_facts(name, text, TODAY)


def test_age_parsing():
    assert extract_age("Date of Birth: 12/05/1996", TODAY) == 30
    assert extract_age("DOB: 3 March 2000", TODAY) == 26
    assert extract_age("Age: 41", TODAY) == 41
    assert extract_age("born 1990", TODAY) == 36
    assert extract_age("no age here", TODAY) is None


def test_years_merge_overlaps_and_present():
    exp = "A, 2018 - 2020\nB, 2019 - 2021\nC, Jan 2024 - Present"
    assert years_of_experience(exp, exp, TODAY) == 5.8  # 2018-2021 (36 months) + Jan 2024 to Nov 2026 (34 months)


def test_stated_years_used():
    assert years_of_experience("", "Over 8 years of relevant experience", TODAY) == 8.0


def test_education_levels_and_facts():
    a = facts(CV_A)
    assert "Diploma" in a.education_levels and "Degree" not in a.education_levels
    assert a.name == "Tendai Moyo" and a.age == 30
    assert a.years_experience and a.years_experience > 8
    assert "Degree" in facts(CV_B).education_levels


def test_education_not_needed_never_fails():
    r = evaluate(facts(CV_A), Requirements(education_level="off", experience_level="must", min_years=3))
    assert r.verdict == "Shortlist"
    edu = next(c for c in r.checks if c.name == "Education")
    assert edu.outcome == "n/a" and edu.detail == "Not required"


def test_must_have_education_filters():
    req = Requirements(education_level="must", education_accepted=["Degree", "Master's"])
    assert evaluate(facts(CV_A), req).verdict == "Not shortlisted"
    assert evaluate(facts(CV_B), req).verdict == "Shortlist"
    req.education_accepted = ["Diploma", "Degree"]  # any one is enough
    assert evaluate(facts(CV_A), req).verdict == "Shortlist"


def test_position_and_licence():
    req = Requirements(position_level="must", positions=["Accountant"],
                       licence_level="must", licences=["Driver's licence"])
    assert evaluate(facts(CV_A), req).verdict == "Shortlist"
    assert evaluate(facts(CV_B), req).verdict == "Not shortlisted"


def test_age_range_and_unknown():
    req = Requirements(age_level="must", age_min=25, age_max=35)
    assert evaluate(facts(CV_A), req).verdict == "Shortlist"
    assert evaluate(facts(CV_B), req).verdict == "Not shortlisted"  # 24
    nodob = facts("Sam Dube\nWork Experience\nClerk 2020 - 2022 at a shop with lots of text to read here")
    assert evaluate(nodob, req).verdict == "Check manually"


def test_preferred_does_not_exclude_but_ranks():
    req = Requirements(experience_level="preferred", min_years=5)
    ranked = rank([evaluate(facts(CV_B), req), evaluate(facts(CV_A), req)])
    assert ranked[0].facts.name == "Tendai Moyo"
    assert all(r.verdict == "Shortlist" for r in ranked)


def test_skills_threshold():
    req = Requirements(skills_level="must", skills=["Python", "SQL", "Tableau"], skills_min_pct=60)
    assert evaluate(facts(CV_B), req).verdict == "Shortlist"  # 2 of 3
    req.skills_min_pct = 100
    assert evaluate(facts(CV_B), req).verdict == "Not shortlisted"


def test_zip_import_and_duplicates():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("cvs/a.txt", CV_A)
        z.writestr("cvs/b.txt", CV_B)
        z.writestr("cvs/copy_of_b.txt", CV_B)
        z.writestr("cvs/photo.jpg", "x")
        z.writestr("__MACOSX/cvs/._a.txt", "x")
    cands, problems = load_candidates([("bundle.zip", buf.getvalue()), ("empty.txt", b"hi")])
    assert sorted(c.name for c in cands) == ["Rudo Ncube", "Tendai Moyo"]
    assert any("identical" in p for p in problems) and any("empty.txt" in p for p in problems)


def test_bad_zip_reported():
    files, problems = expand_uploads([("x.zip", b"not a zip")])
    assert files == [] and problems
