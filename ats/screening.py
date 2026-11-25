"""Screen many CVs against a company's requirements.

Each requirement (education, experience, position, licence, age, skills) can be
set to "off" (not needed), "preferred" (nice to have) or "must" (must have).
A CV that fails any "must" is not shortlisted. Everything else is ranked by a
score built from the requirements that are switched on.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from functools import lru_cache

from .analyzer import _count_alias
from .skills import all_skills

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

EDU_PATTERNS: dict[str, re.Pattern] = {
    name: re.compile(pattern, re.I)
    for name, pattern in {
        "Secondary (O/A Level)": r"\b(o[\s-]?levels?|a[\s-]?levels?|zimsec|grade 12|high school|matric|secondary school|igcse)\b",
        "Certificate / short course": r"\b(certificate|certification|certified|short course|national certificate)\b",
        "Training / apprenticeship": r"\b(training|trained|apprenticeship|trade test|vocational|traineeship)\b",
        "Diploma": r"\b(diploma|higher national diploma|hnd|national diploma)\b",
        "Degree": r"\b(bachelor'?s?|b\.?sc|b\.?eng|b\.?com|bba|llb|degree|honours|hons)\b",
        "Master's": r"\b(master'?s?|m\.?sc|mba|m\.?phil|postgraduate)\b",
        "PhD": r"\b(ph\.?d|doctorate|doctoral)\b",
    }.items()
}
EDU_ORDER = list(EDU_PATTERNS)

LICENCES: dict[str, list[str]] = {
    "Driver's licence": ["driver's licence", "driver's license", "drivers licence", "drivers license",
                         "driving licence", "driving license", "clean licence", "clean license",
                         "class 4", "class 2", "class 1", "code 14"],
    "Forklift licence": ["forklift"],
    "First aid certificate": ["first aid"],
    "Professional registration": ["registered with", "registration number", "professional registration", "council registration"],
    "CPA / ACCA / CIMA": ["cpa", "acca", "cima", "chartered accountant"],
}

LEVELS = ("off", "preferred", "must")
WEIGHTS = {"Education": 20, "Experience": 25, "Position": 15, "Licence": 15, "Age": 10, "Skills": 15}

_SECTION_HEAD = re.compile(
    r"^[\W_]*(?:profile|personal profile|professional summary|summary|objective|career objective|education|"
    r"academic background|academic qualifications|qualifications|(?:work |professional |relevant )?experience|"
    r"employment(?: history)?|work history|career history|internships?|(?:technical |key |core )?skills|"
    r"projects|certifications?|licen[cs]es?|references?|referees|languages|interests|hobbies|"
    r"personal (?:details|information)|achievements|training)[\W_]*$",
    re.I,
)
_MONTHS = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
_RANGE = re.compile(
    r"(?:(?P<m1>[A-Za-z]{3,9})\.?\s+|(?P<n1>\d{1,2})[/.\-])?(?P<y1>(?:19|20)\d{2})\s*(?:-|–|—|to|until)\s*"
    r"(?:(?:(?P<m2>[A-Za-z]{3,9})\.?\s+|(?P<n2>\d{1,2})[/.\-])?(?P<y2>(?:19|20)\d{2})"
    r"|(?P<now>present|current|date|now|ongoing|today))",
    re.I,
)
_STATED_YEARS = re.compile(r"(\d{1,2})\+?\s*years?(?:['’]s)?\s*(?:of\s+)?(?:\w+\s+){0,3}experience", re.I)

# ---------------------------------------------------------------------------
# Reading facts out of a CV
# ---------------------------------------------------------------------------


@dataclass
class CandidateFacts:
    filename: str
    name: str
    email: str
    phone: str
    text: str
    exp_text: str
    education_levels: list[str]
    years_experience: float | None
    age: int | None
    age_source: str = ""  # 'date of birth', 'stated age' or ''


def split_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    name, buf = "header", []
    for line in text.splitlines():
        s = line.strip()
        if s and len(s) <= 40 and _SECTION_HEAD.match(s):
            sections.append((name, "\n".join(buf)))
            name, buf = s.lower().strip(": "), []
        else:
            buf.append(line)
    sections.append((name, "\n".join(buf)))
    return sections


def experience_text(sections: list[tuple[str, str]]) -> str:
    exp = [t for n, t in sections if re.search(r"experience|employment|work history|career|internship", n)]
    if exp:
        return "\n".join(exp)
    return "\n".join(t for n, t in sections if not re.search(r"education|academic|qualif|referee|reference", n))


def education_levels(text: str) -> list[str]:
    return [lvl for lvl, pat in EDU_PATTERNS.items() if pat.search(text)]


def _month(word: str | None, num: str | None) -> int | None:
    if word and word[:3].lower() in _MONTHS:
        return _MONTHS[word[:3].lower()]
    if num and 1 <= int(num) <= 12:
        return int(num)
    return None


def years_of_experience(exp_text: str, full_text: str, today: dt.date | None = None) -> float | None:
    """Years of experience from dated roles (overlaps merged) or a statement like '5 years experience'."""
    today = today or dt.date.today()
    now_idx = today.year * 12 + today.month - 1
    spans: list[tuple[int, int]] = []
    for m in _RANGE.finditer(exp_text):
        y1 = int(m["y1"])
        m1 = _month(m["m1"], m["n1"])
        if m["now"]:
            start, end = y1 * 12 + (m1 or 1) - 1, now_idx
        else:
            y2, m2 = int(m["y2"]), _month(m["m2"], m["n2"])
            start = y1 * 12 + (m1 or m2 or 1) - 1
            end = y2 * 12 + (m2 or m1 or 1) - 1 + (1 if m1 and m2 else 0)
            if end <= start and y2 == y1:
                end = start + 6
        if end <= start or y1 < 1970 or end > now_idx + 12:
            continue
        spans.append((start, end))
    spans.sort()
    merged: list[list[int]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    from_dates = sum(e - s for s, e in merged) / 12 if merged else None
    stated = [int(x) for x in _STATED_YEARS.findall(full_text) if 0 < int(x) <= 50]
    values = [v for v in (from_dates, float(max(stated)) if stated else None) if v is not None]
    return round(max(values), 1) if values else None


_DOB_LABEL = re.compile(
    r"\b(?:date\s*of\s*birth|birth\s*date|birthdate|birthday|d\.?\s?o\.?\s?b|born(?:\s+(?:on|in))?|birth)"
    r"(?![A-Za-z])\.?\s*[:\-|–]?\s*([^\n]{0,40})",
    re.I,
)


def _month_num(word: str) -> int | None:
    return _MONTHS.get(word[:3].lower()) if len(word) >= 3 else None


def parse_birth_date(chunk: str, today: dt.date) -> tuple[int, int | None, int | None] | None:
    """Find (year, month, day) in text such as '12/03/1998', '12th March 1998', '1998-03-12', 'March 1998', '1998'.
    Month and day are None when the CV does not give them. Numeric dates are read day first (12/03 = 12 March)
    unless the second number cannot be a month."""
    m = re.search(r"\b((?:19|20)\d{2})[/.\-](\d{1,2})[/.\-](\d{1,2})\b", chunk)  # 1998-03-12
    if m and 1 <= int(m[2]) <= 12 and 1 <= int(m[3]) <= 31:
        return int(m[1]), int(m[2]), int(m[3])
    m = re.search(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4}|\d{2})\b", chunk)  # 12/03/1998 or 12/03/98
    if m:
        day, month, yr = int(m[1]), int(m[2]), int(m[3])
        if month > 12 >= day:
            day, month = month, day  # written month first
        if len(m[3]) == 2:
            yr += 1900 if yr > today.year % 100 else 2000
        if 1 <= month <= 12 and 1 <= day <= 31:
            return yr, month, day
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s*(?:of\s+)?([A-Za-z]{3,9})\.?,?\s+((?:19|20)\d{2})\b", chunk)  # 12 March 1998
    if m and _month_num(m[2]) and 1 <= int(m[1]) <= 31:
        return int(m[3]), _month_num(m[2]), int(m[1])
    m = re.search(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+((?:19|20)\d{2})\b", chunk)  # March 12, 1998
    if m and _month_num(m[1]) and 1 <= int(m[2]) <= 31:
        return int(m[3]), _month_num(m[1]), int(m[2])
    m = re.search(r"\b([A-Za-z]{3,9})\.?\s+((?:19|20)\d{2})\b", chunk)  # March 1998
    if m and _month_num(m[1]):
        return int(m[2]), _month_num(m[1]), None
    m = re.search(r"\b((?:19|20)\d{2})\b", chunk)  # 1998
    return (int(m[1]), None, None) if m else None


def extract_age_info(text: str, today: dt.date | None = None) -> tuple[int | None, str]:
    """Return (age, source). The age is worked out from a date of birth when the CV has one,
    otherwise taken from a stated age such as 'Age: 27'. Source is 'date of birth', 'stated age' or ''."""
    today = today or dt.date.today()

    def valid(a: int) -> int | None:
        return a if 14 <= a <= 80 else None

    for m in _DOB_LABEL.finditer(text):
        found = parse_birth_date(m.group(1), today)
        if not found:
            continue
        year, month, day = found
        age = today.year - year
        if month:  # birthday not reached yet this year (assume mid-month when the day is missing)
            age -= (today.month, today.day) < (month, day or 15)
        age = valid(age)
        if age is not None:
            return age, "date of birth"
    m = re.search(r"\bage\s*[:\-]?\s*(\d{2})\b", text, re.I) or re.search(
        r"\b(\d{2})\s*(?:years?\s*old|yrs?\s*old|y/o)\b", text, re.I
    )
    if m and (age := valid(int(m.group(1)))) is not None:
        return age, "stated age"
    return None, ""


def extract_age(text: str, today: dt.date | None = None) -> int | None:
    return extract_age_info(text, today)[0]


def guess_name(text: str, fallback: str) -> str:
    for line in text.splitlines()[:6]:
        line = line.strip()
        if re.fullmatch(r"[A-Za-z][A-Za-z'’.\-]+(?:\s+[A-Za-z][A-Za-z'’.\-]+){1,3}", line) and not re.search(
            r"curriculum|vitae|resume|\bcv\b|profile|education|experience|summary", line, re.I
        ):
            return line.title() if line.isupper() else line
    return fallback


def extract_facts(filename: str, text: str, today: dt.date | None = None) -> CandidateFacts:
    sections = split_sections(text)
    exp = experience_text(sections)
    age, age_source = extract_age_info(text, today)
    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    phone = re.search(r"\+?\d[\d \-()]{8,}\d", text)
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", filename.split("/")[-1]).replace("_", " ").replace("-", " ")
    return CandidateFacts(
        filename=filename,
        name=guess_name(text, stem),
        email=email.group(0) if email else "",
        phone=phone.group(0).strip() if phone else "",
        text=text,
        exp_text=exp,
        education_levels=education_levels(text),
        years_experience=years_of_experience(exp, text, today),
        age=age,
        age_source=age_source,
    )


# ---------------------------------------------------------------------------
# Requirements and matching
# ---------------------------------------------------------------------------


@dataclass
class Requirements:
    education_level: str = "off"
    education_accepted: list[str] = field(default_factory=list)  # any one of these is enough
    education_must: list[str] = field(default_factory=list)  # every one of these is needed
    education_fields: list[str] = field(default_factory=list)  # optional subjects, any one is enough
    experience_level: str = "off"
    min_years: float = 0.0
    max_years: float | None = None
    position_level: str = "off"
    positions: list[str] = field(default_factory=list)  # any one of these job titles
    licence_level: str = "off"
    licences: list[str] = field(default_factory=list)
    licence_all: bool = True  # need every licence listed, or just any one
    age_level: str = "off"
    age_min: int | None = None
    age_max: int | None = None
    skills_level: str = "off"
    skills: list[str] = field(default_factory=list)
    skills_min_pct: int = 70


@dataclass
class Check:
    name: str
    level: str  # off / preferred / must
    outcome: str  # pass / fail / unknown / n/a
    detail: str
    fraction: float = 0.0


@dataclass
class ScreenResult:
    facts: CandidateFacts
    score: int
    verdict: str  # Shortlist / Check manually / Not shortlisted
    checks: list[Check]

    @property
    def failed_musts(self) -> list[str]:
        return [c.name for c in self.checks if c.level == "must" and c.outcome == "fail"]


@lru_cache(maxsize=512)
def _aliases(term: str) -> tuple[str, ...]:
    t = term.strip().lower()
    for group in all_skills().values():
        for name, aliases in group.items():
            if t == name.lower() or t in {a.lower().removeprefix("cs:") for a in aliases}:
                return tuple(aliases) + (name,)
    for name, aliases in LICENCES.items():
        if t == name.lower():
            return tuple(aliases)
    return (term.strip(),)


def term_present(term: str, text: str) -> bool:
    return any(_count_alias(a, text) for a in _aliases(term) if a)


def _na(name: str) -> Check:
    return Check(name, "off", "n/a", "Not required")


def _check_education(f: CandidateFacts, r: Requirements) -> Check:
    if r.education_level == "off":
        return _na("Education")
    fracs, notes = [], []
    if r.education_accepted:
        ok = [lvl for lvl in r.education_accepted if lvl in f.education_levels]
        fracs.append(1.0 if ok else 0.0)
        notes.append(("has " + ", ".join(ok)) if ok else "no accepted qualification found")
    if r.education_must:
        have = [lvl for lvl in r.education_must if lvl in f.education_levels]
        fracs.append(len(have) / len(r.education_must))
        missing = [lvl for lvl in r.education_must if lvl not in have]
        notes.append("missing " + ", ".join(missing) if missing else "has " + ", ".join(have))
    fields_ = [x for x in r.education_fields if term_present(x, f.text)]
    if r.education_fields:
        fracs.append(1.0 if fields_ else 0.0)
        notes.append(("field: " + ", ".join(fields_)) if fields_ else "required field of study not found")
    if not fracs:
        return _na("Education")
    frac = sum(fracs) / len(fracs)
    return Check("Education", r.education_level, "pass" if frac == 1 else "fail", "; ".join(notes), frac)


def _check_experience(f: CandidateFacts, r: Requirements) -> Check:
    if r.experience_level == "off":
        return _na("Experience")
    yrs = f.years_experience
    if yrs is None:
        if r.min_years <= 0:
            return Check("Experience", r.experience_level, "pass", "no minimum asked", 1.0)
        return Check("Experience", r.experience_level, "unknown", "no dated roles found, check the CV", 0.0)
    if yrs < r.min_years:
        return Check("Experience", r.experience_level, "fail", f"{yrs:g} yrs (needs {r.min_years:g}+)", yrs / r.min_years)
    if r.max_years is not None and yrs > r.max_years:
        return Check("Experience", r.experience_level, "fail", f"{yrs:g} yrs (max {r.max_years:g})", 0.5)
    return Check("Experience", r.experience_level, "pass", f"{yrs:g} yrs", 1.0)


def _check_position(f: CandidateFacts, r: Requirements) -> Check:
    if r.position_level == "off" or not r.positions:
        return _na("Position")
    hay = f.exp_text or f.text
    hits = [p for p in r.positions if term_present(p, hay)]
    return Check("Position", r.position_level, "pass" if hits else "fail",
                 ("held: " + ", ".join(hits)) if hits else "no matching job title in experience", 1.0 if hits else 0.0)


def _check_licence(f: CandidateFacts, r: Requirements) -> Check:
    if r.licence_level == "off" or not r.licences:
        return _na("Licence")
    have = [x for x in r.licences if term_present(x, f.text)]
    missing = [x for x in r.licences if x not in have]
    ok = not missing if r.licence_all else bool(have)
    detail = ("has " + ", ".join(have)) if ok else ("missing " + ", ".join(missing if r.licence_all else r.licences))
    return Check("Licence", r.licence_level, "pass" if ok else "fail", detail, len(have) / len(r.licences))


def _check_age(f: CandidateFacts, r: Requirements) -> Check:
    if r.age_level == "off" or (r.age_min is None and r.age_max is None):
        return _na("Age")
    src = " (from date of birth)" if f.age_source == "date of birth" else ""
    if f.age is None:
        return Check("Age", r.age_level, "unknown", "no age or date of birth on CV", 0.0)
    if r.age_min is not None and f.age < r.age_min:
        return Check("Age", r.age_level, "fail", f"{f.age}{src} (min {r.age_min})", 0.0)
    if r.age_max is not None and f.age > r.age_max:
        return Check("Age", r.age_level, "fail", f"{f.age}{src} (max {r.age_max})", 0.0)
    return Check("Age", r.age_level, "pass", f"{f.age}{src}", 1.0)


def _check_skills(f: CandidateFacts, r: Requirements) -> Check:
    if r.skills_level == "off" or not r.skills:
        return _na("Skills")
    have = [s for s in r.skills if term_present(s, f.text)]
    frac = len(have) / len(r.skills)
    ok = frac * 100 >= r.skills_min_pct
    missing = [s for s in r.skills if s not in have]
    detail = f"{len(have)}/{len(r.skills)}" + (f", missing {', '.join(missing[:4])}" + ("…" if len(missing) > 4 else "") if missing else "")
    return Check("Skills", r.skills_level, "pass" if ok else "fail", detail, frac)


def evaluate(f: CandidateFacts, r: Requirements) -> ScreenResult:
    checks = [
        _check_education(f, r), _check_experience(f, r), _check_position(f, r),
        _check_licence(f, r), _check_age(f, r), _check_skills(f, r),
    ]
    active = [c for c in checks if c.level != "off" and c.outcome != "unknown"]
    total = sum(WEIGHTS[c.name] for c in active)
    score = round(sum(WEIGHTS[c.name] * c.fraction for c in active) / total * 100) if total else 100
    musts = [c for c in checks if c.level == "must"]
    if any(c.outcome == "fail" for c in musts):
        verdict = "Not shortlisted"
    elif any(c.outcome == "unknown" for c in musts):
        verdict = "Check manually"
    else:
        verdict = "Shortlist"
    return ScreenResult(f, score, verdict, checks)


VERDICT_ORDER = {"Shortlist": 0, "Check manually": 1, "Not shortlisted": 2}


def rank(results: list[ScreenResult]) -> list[ScreenResult]:
    return sorted(results, key=lambda r: (VERDICT_ORDER[r.verdict], -r.score, r.facts.name.lower()))
