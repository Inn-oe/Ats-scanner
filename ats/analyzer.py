"""Compare a CV against a job advert and explain how well it matches.

Everything here is rule based and runs offline. The goal is to behave like the
keyword filters most applicant tracking systems (ATS) use, and then add the
kind of feedback a careers adviser would give.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

from .skills import DEGREE_SUBJECTS, EDUCATION_TERMS, all_skills

# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

STOPWORDS = set(
    """a about above after again against all also am an and any are as at be because been before being
    below between both but by can could did do does doing down during each etc few for from further had has
    have having he her here hers him his how i if in into is it its itself just me more most my no nor not
    of off on once only or other our ours out over own same she should so some such than that the their
    theirs them then there these they this those through to too under until up very was we were what when
    where which while who whom why will with would you your yours yourself within across per via e.g i.e
    including include includes including us may must shall well new one two three like least""".split()
)

# Words that appear in almost every job advert and say nothing about the role.
JOB_AD_NOISE = set(
    """role roles job jobs candidate candidates applicant applicants company organisation organization
    business team teams work working opportunity opportunities apply application applications position
    successful ideal looking join joining based salary benefits package offer offering please closing date
    responsibilities responsibility requirements required requirement essential desirable preferred
    experience skills skill ability able strong good excellent knowledge understanding key day days week
    weeks year years month months time full part within help support ensure using use used make provide
    graduate graduates programme program scheme trainee trainees employer equal people person want need
    hours location remote hybrid office career careers develop development growth great world leading
    across range variety environment level levels plus bonus etc advantage clearly large related subject
    several would could strong ability relevant similar field areas area various multiple other ensure""".split()
)

DESIRABLE_MARKERS = re.compile(
    r"\b(desirable|nice to have|nice-to-have|advantage|advantageous|preferred|preferably|bonus|plus|"
    r"ideally|beneficial|would be great|not essential|a plus)\b",
    re.I,
)

ACTION_VERBS = set(
    """achieved analysed analyzed automated built collaborated created delivered designed developed
    engineered evaluated forecasted identified implemented improved increased launched led managed
    modelled modeled optimised optimized organised organized presented produced reduced researched
    resolved saved streamlined trained visualised visualized wrote cleaned deployed coordinated
    conducted investigated mentored negotiated predicted processed scraped tested validated won""".split()
)

WEAK_PHRASES = [
    "responsible for", "duties included", "worked on", "helped with", "assisted with", "involved in",
    "tasked with", "hard worker", "hardworking", "team player", "go-getter", "think outside the box",
]

SECTION_PATTERNS = {
    "Contact details": r"(@|\+?\d[\d \-()]{7,}\d)",
    "Profile / summary": r"^\s*(profile|personal profile|professional summary|summary|about me|personal statement|career objective|objective)\b",
    "Education": r"^\s*(education|academic|qualifications|academic background)\b",
    "Experience": r"^\s*(experience|work experience|professional experience|employment|employment history|work history|internships?)\b",
    "Skills": r"^\s*(skills|technical skills|key skills|core skills|competencies|core competencies|tools)\b",
    "Projects": r"^\s*(projects|personal projects|academic projects|portfolio|selected projects)\b",
}


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _stem(word: str) -> str:
    for suffix in ("isation", "ization", "ations", "ation", "ings", "ing", "ies", "ers", "ed", "es", "s", "er"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z+#.\-]*[a-zA-Z+#]|[a-zA-Z]", text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def _alias_pattern(alias: str) -> re.Pattern:
    if alias.startswith("cs:"):
        return re.compile(r"(?<![\w&/])" + re.escape(alias[3:]) + r"(?![\w&/])")
    escaped = re.escape(alias.lower()).replace(r"\ ", r"[\s\-]+")
    return re.compile(r"(?<![\w])" + escaped + r"(?![\w])", re.I)


_PATTERN_CACHE: dict[str, re.Pattern] = {}


def _count_alias(alias: str, text: str) -> int:
    if alias not in _PATTERN_CACHE:
        _PATTERN_CACHE[alias] = _alias_pattern(alias)
    return len(_PATTERN_CACHE[alias].findall(text))


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?;])\s+|\n+|•", text)
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class SkillMatch:
    name: str
    category: str  # "technical" or "soft"
    importance: str  # "required", "desirable", or "alternative" (an either/or option you already cover)
    found: bool
    cv_mentions: int = 0


@dataclass
class Suggestion:
    priority: str  # "high", "medium", "low"
    text: str


@dataclass
class AnalysisResult:
    score: int
    verdict: str
    breakdown: dict[str, float]
    skills: list[SkillMatch]
    keywords_found: list[str]
    keywords_missing: list[str]
    extra_cv_skills: list[str]
    checks: dict[str, bool]
    stats: dict[str, object]
    suggestions: list[Suggestion] = field(default_factory=list)

    @property
    def matched_skills(self) -> list[SkillMatch]:
        return [s for s in self.skills if s.found]

    @property
    def missing_skills(self) -> list[SkillMatch]:
        return [s for s in self.skills if not s.found]

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "verdict": self.verdict,
            "breakdown": self.breakdown,
            "matched_skills": [s.__dict__ for s in self.matched_skills],
            "missing_skills": [s.__dict__ for s in self.missing_skills],
            "keywords_found": self.keywords_found,
            "keywords_missing": self.keywords_missing,
            "extra_cv_skills": self.extra_cv_skills,
            "checks": self.checks,
            "stats": self.stats,
            "suggestions": [s.__dict__ for s in self.suggestions],
        }


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------


def find_skills(text: str) -> dict[str, tuple[str, int]]:
    """Return {skill name: (category, number of mentions)} for skills in text."""
    found: dict[str, tuple[str, int]] = {}
    for category, skills in all_skills().items():
        for name, aliases in skills.items():
            count = sum(_count_alias(a, text) for a in aliases)
            if count:
                found[name] = (category, count)
    return found


def _skill_importance(name: str, category: str, job_text: str) -> str:
    """A skill is 'desirable' if every sentence that names it is marked as optional."""
    aliases = all_skills()[category][name]
    sentences = [s for s in _sentences(job_text) if any(_count_alias(a, s) for a in aliases)]
    if sentences and all(DESIRABLE_MARKERS.search(s) for s in sentences):
        return "desirable"
    return "required"


def _mark_alternatives(skills: list[SkillMatch], job_text: str) -> None:
    """Handle 'Python or R': if you have one option, the other is not counted as missing."""
    found = {s.name for s in skills if s.found}
    by_name = {s.name: s for s in skills}
    for s in skills:
        if s.found:
            continue
        aliases = all_skills()[s.category][s.name]
        for sentence in _sentences(job_text):
            if not any(_count_alias(a, sentence) for a in aliases) or not re.search(r"\bor\b|/", sentence):
                continue
            others = [n for n in found if n != s.name and any(
                _count_alias(a, sentence) for a in all_skills()[by_name[n].category][n])]
            if others:
                s.importance = "alternative"
                break


def extract_keywords(job_text: str, known_skill_text: str = "", limit: int = 15) -> list[str]:
    """Pick the job advert's most repeated meaningful words and two-word phrases.

    Words already covered by a matched skill are left out so they are not
    counted twice.
    """
    tokens = [t for t in _tokens(job_text) if t not in JOB_AD_NOISE and not t.isdigit()]
    skill_words = set(_tokens(known_skill_text))
    unigrams = Counter(t for t in tokens if t not in skill_words and len(t) > 2)
    bigrams = Counter(
        f"{a} {b}" for a, b in zip(tokens, tokens[1:]) if a not in skill_words or b not in skill_words
    )
    candidates: list[tuple[str, float]] = []
    for phrase, n in bigrams.items():
        if n >= 2:
            candidates.append((phrase, n * 1.6))
    for word, n in unigrams.items():
        candidates.append((word, float(n)))
    candidates.sort(key=lambda x: (-x[1], x[0]))

    chosen: list[str] = []
    for phrase, _ in candidates:
        if any(phrase in c or c in phrase.split() for c in chosen):
            continue
        chosen.append(phrase)
        if len(chosen) >= limit:
            break
    return chosen


def _keyword_in(keyword: str, text_stems: set[str], text_lower: str) -> bool:
    if keyword in text_lower:
        return True
    return all(_stem(w) in text_stems for w in keyword.split())


def similarity(a: str, b: str) -> float:
    """Cosine similarity of stemmed word counts (0 to 1)."""
    ca = Counter(_stem(t) for t in _tokens(a) if t not in JOB_AD_NOISE)
    cb = Counter(_stem(t) for t in _tokens(b) if t not in JOB_AD_NOISE)
    if not ca or not cb:
        return 0.0
    dot = sum(ca[k] * cb[k] for k in ca.keys() & cb.keys())
    norm = math.sqrt(sum(v * v for v in ca.values())) * math.sqrt(sum(v * v for v in cb.values()))
    return dot / norm if norm else 0.0


def _education_requirements(job_text: str) -> tuple[list[str], list[str]]:
    levels = [lvl for lvl, aliases in EDUCATION_TERMS.items() if any(_count_alias(a, job_text) for a in aliases)]
    subjects = [s for s in DEGREE_SUBJECTS if _count_alias(s, job_text)]
    return levels, subjects


def _years_required(job_text: str) -> int | None:
    m = re.findall(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?(?:years?|yrs?)(?:'|’)?\s*(?:of\s+)?(?:relevant\s+|professional\s+|work\s+)?experience", job_text, re.I)
    return min(int(x) for x in m) if m else None


def _cv_checks(cv_text: str) -> tuple[dict[str, bool], dict[str, object]]:
    lower = cv_text.lower()
    words = re.findall(r"\b\w+\b", cv_text)
    lines = [ln.strip() for ln in cv_text.splitlines() if ln.strip()]
    bullet_like = [ln for ln in lines if len(ln.split()) >= 5]
    quantified = [ln for ln in bullet_like if re.search(r"\d+\s*%|\d{2,}|£|\$|€|\b\d+(\.\d+)?\s*(k|m|x)\b", ln, re.I)]
    starts_with_verb = [ln for ln in bullet_like if ln.lstrip("•-*– ").split(" ")[0].lower().strip(",.") in ACTION_VERBS]
    weak = [p for p in WEAK_PHRASES if p in lower]
    pronouns = len(re.findall(r"\b(i|me|my)\b", lower))

    checks = {
        "Email address": bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", cv_text)),
        "Phone number": bool(re.search(r"\+?\d[\d \-()]{8,}\d", cv_text)),
        "LinkedIn profile": "linkedin" in lower,
        "GitHub or portfolio link": bool(re.search(r"github|gitlab|kaggle|portfolio|https?://", lower)),
    }
    for section, pattern in SECTION_PATTERNS.items():
        if section == "Contact details":
            continue
        checks[f"{section} section"] = bool(re.search(pattern, cv_text, re.I | re.M))
    checks["Readable length (350-1000 words)"] = 350 <= len(words) <= 1000
    checks["Achievements with numbers"] = len(quantified) >= 3
    checks["Bullets start with action verbs"] = len(starts_with_verb) >= 3
    checks["No weak or cliché phrases"] = not weak

    stats = {
        "word_count": len(words),
        "quantified_lines": len(quantified),
        "action_verb_lines": len(starts_with_verb),
        "weak_phrases": weak,
        "first_person_words": pronouns,
    }
    return checks, stats


def _job_title(job_text: str) -> str | None:
    for line in job_text.splitlines():
        line = line.strip(" :-*#\t")
        if 3 <= len(line) <= 70 and len(line.split()) <= 8 and not line.endswith("."):
            return line
    return None


def analyze(cv_text: str, job_text: str) -> AnalysisResult:
    if not cv_text.strip():
        raise ValueError("The CV is empty. If it is a scanned PDF, export it again as a text-based PDF or DOCX.")
    if not job_text.strip():
        raise ValueError("Add the job advert or the list of qualities you want to match.")

    cv_lower = _normalise(cv_text)
    cv_stems = {_stem(t) for t in _tokens(cv_text)}

    # 1. Skills -------------------------------------------------------------
    job_skills = find_skills(job_text)
    cv_skills = find_skills(cv_text)
    skills: list[SkillMatch] = []
    for name, (category, _) in job_skills.items():
        importance = _skill_importance(name, category, job_text)
        mentions = cv_skills.get(name, (category, 0))[1]
        skills.append(SkillMatch(name, category, importance, mentions > 0, mentions))
    _mark_alternatives(skills, job_text)
    skills.sort(key=lambda s: (s.found, s.importance != "required", s.category != "technical", s.name))

    def weight(s: SkillMatch) -> float:
        base = {"required": 1.0, "desirable": 0.5}.get(s.importance, 0.0)
        return base * (1.0 if s.category == "technical" else 0.7)

    total_w = sum(weight(s) for s in skills)
    skill_score = sum(weight(s) for s in skills if s.found) / total_w if total_w else None

    extra_cv_skills = sorted(n for n, (cat, _) in cv_skills.items() if n not in job_skills and cat == "technical")

    # 2. Keywords -------------------------------------------------------------
    skill_alias_text = " ".join(
        " ".join(a.replace("cs:", "") for a in all_skills()[cat][n]) + " " + n for n, (cat, _) in job_skills.items()
    )
    edu_text = " ".join(DEGREE_SUBJECTS) + " " + " ".join(" ".join(v) for v in EDUCATION_TERMS.values())
    keywords = extract_keywords(job_text, skill_alias_text + " " + edu_text)
    kw_found = [k for k in keywords if _keyword_in(k, cv_stems, cv_lower)]
    kw_missing = [k for k in keywords if k not in kw_found]
    keyword_score = len(kw_found) / len(keywords) if keywords else None

    # 3. Overall wording similarity -------------------------------------------
    sim = similarity(cv_text, job_text)
    sim_score = min(1.0, sim / 0.6)

    # 4. Education ------------------------------------------------------------
    levels, subjects = _education_requirements(job_text)
    edu_parts = []
    if levels:
        edu_parts.append(any(any(_count_alias(a, cv_text) for a in EDUCATION_TERMS[lvl]) for lvl in levels))
    if subjects:
        edu_parts.append(any(_count_alias(s, cv_text) for s in subjects))
    edu_score = sum(edu_parts) / len(edu_parts) if edu_parts else None

    # 5. CV quality -----------------------------------------------------------
    checks, stats = _cv_checks(cv_text)
    quality_score = sum(checks.values()) / len(checks)

    # Combine, re-spreading weight from parts that do not apply ---------------
    parts = {
        "Skills match": (skill_score, 45),
        "Keyword match": (keyword_score, 20),
        "Overall relevance": (sim_score, 10),
        "Education fit": (edu_score, 10),
        "CV structure & impact": (quality_score, 15),
    }
    active = {k: v for k, v in parts.items() if v[0] is not None}
    weight_sum = sum(w for _, w in active.values())
    score = round(sum(val * w for val, w in active.values()) / weight_sum * 100)
    breakdown = {k: round(v[0] * 100) for k, v in active.items()}

    if score >= 80:
        verdict = "Strong match. This CV should get past most ATS keyword filters."
    elif score >= 65:
        verdict = "Good match. A few targeted edits will make it stronger."
    elif score >= 45:
        verdict = "Partial match. Tailor the CV to this advert before applying."
    else:
        verdict = "Weak match. Either the role is a stretch or the CV needs heavy tailoring."

    stats.update(
        {
            "similarity": round(sim, 3),
            "years_required": _years_required(job_text),
            "education_levels_asked": levels,
            "degree_subjects_asked": subjects,
            "job_title": _job_title(job_text),
        }
    )

    result = AnalysisResult(
        score=score,
        verdict=verdict,
        breakdown=breakdown,
        skills=skills,
        keywords_found=kw_found,
        keywords_missing=kw_missing,
        extra_cv_skills=extra_cv_skills,
        checks=checks,
        stats=stats,
    )
    result.suggestions = build_suggestions(result, cv_text)
    return result


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------


def build_suggestions(r: AnalysisResult, cv_text: str) -> list[Suggestion]:
    out: list[Suggestion] = []
    missing_req_tech = [s.name for s in r.missing_skills if s.importance == "required" and s.category == "technical"]
    alternatives = [s.name for s in r.missing_skills if s.importance == "alternative"]
    missing_des_tech = [s.name for s in r.missing_skills if s.importance == "desirable" and s.category == "technical"]
    missing_soft = [s.name for s in r.missing_skills if s.category == "soft" and s.importance != "alternative"]
    thin = [s.name for s in r.matched_skills if s.importance == "required" and s.cv_mentions == 1]

    if missing_req_tech:
        out.append(Suggestion("high",
            f"The advert asks for {_join(missing_req_tech)}, which your CV does not mention. If you have used them "
            "(in a course, dissertation, project or job), add them to your Skills section using the same words "
            "as the advert, and show where you used them in a bullet point."))
    if alternatives:
        out.append(Suggestion("low",
            f"The advert accepts either/or options and you already cover one. Adding {_join(alternatives)} would "
            "still help if you have used it."))
    if missing_soft:
        out.append(Suggestion("high",
            f"Show evidence of {_join(missing_soft)}. Recruiters skip claims like 'good communicator', so write "
            "a bullet that proves it, for example 'Presented churn analysis to 12 non-technical managers, "
            "leading to a new retention campaign'."))
    if r.keywords_missing:
        out.append(Suggestion("medium",
            f"Work these words from the advert into your CV where they are true for you: "
            f"{_join(r.keywords_missing[:8])}. ATS filters often look for the exact wording."))
    if thin:
        out.append(Suggestion("medium",
            f"{_join(thin)} appear only once in your CV. Mention each again in a project or experience bullet "
            "so it is backed by evidence, not only listed."))
    if missing_des_tech:
        out.append(Suggestion("low",
            f"Nice-to-haves you could add if you have any exposure: {_join(missing_des_tech)}. Even a short "
            "online course or a small project counts for graduate roles."))

    c, st = r.checks, r.stats
    if not c.get("Achievements with numbers"):
        out.append(Suggestion("high",
            f"Only {st['quantified_lines']} lines contain numbers. Quantify results: dataset sizes, accuracy, time "
            "saved, % improvement, number of users or stakeholders (e.g. 'Cleaned 50k-row sales dataset and built "
            "a Power BI dashboard used weekly by 3 managers')."))
    if not c.get("Bullets start with action verbs"):
        out.append(Suggestion("medium",
            "Start bullet points with strong past-tense verbs such as Built, Analysed, Automated, Forecasted, "
            "Presented or Improved."))
    if st["weak_phrases"]:
        out.append(Suggestion("medium",
            f"Replace weak phrases ({_join(st['weak_phrases'])}) with what you achieved. For example, change "
            "'Responsible for reports' to 'Produced 4 weekly sales reports that cut manual work by 3 hours'."))
    if not c.get("Profile / summary section"):
        title = st.get("job_title") or "the role"
        top = [s.name for s in r.matched_skills if s.category == "technical"][:4]
        out.append(Suggestion("medium",
            f"Add a 2-3 line profile at the top aimed at {title}. Name your degree and your strongest matching "
            f"skills{(' (' + _join(top) + ')') if top else ''}."))
    if not c.get("Projects section"):
        out.append(Suggestion("medium",
            "Add a Projects section. For data graduates, 2-3 projects with a GitHub link, the tools used and a "
            "measurable result are often worth more than unrelated work experience."))
    if not c.get("Skills section"):
        out.append(Suggestion("high", "Add a clearly titled 'Skills' section. ATS systems look for it to read your tools and languages."))
    if not c.get("Experience section"):
        out.append(Suggestion("medium", "Add an 'Experience' section (internships, attachments, part-time work and volunteering all count)."))
    if not c.get("Education section"):
        out.append(Suggestion("high", "Add an 'Education' section with your degree, university, dates and classification."))
    for item in ("Email address", "Phone number", "LinkedIn profile"):
        if not c.get(item):
            out.append(Suggestion("high" if item != "LinkedIn profile" else "low", f"Add your {item.lower()} to the header."))
    if not c.get("GitHub or portfolio link"):
        out.append(Suggestion("low", "Add a GitHub, Kaggle or portfolio link so recruiters can see your code."))
    wc = st["word_count"]
    if wc < 350:
        out.append(Suggestion("medium", f"The CV is short ({wc} words). Expand your projects and experience with results."))
    elif wc > 1000:
        out.append(Suggestion("medium", f"The CV is long ({wc} words). Aim for 2 pages and cut content that does not match the role."))
    if st["first_person_words"] > 5:
        out.append(Suggestion("low", "Drop 'I', 'me' and 'my' from bullet points. CVs read better in implied first person."))
    if st.get("years_required"):
        out.append(Suggestion("medium",
            f"The advert mentions {st['years_required']}+ years of experience. Make dates clear for every role, and "
            "count internships, research assistant work and long projects where they are relevant."))
    if r.stats.get("degree_subjects_asked") and r.breakdown.get("Education fit", 100) < 100:
        out.append(Suggestion("high",
            f"The advert asks for a degree in {_join(r.stats['degree_subjects_asked'])}. Write your degree title in full "
            "and list relevant modules if your degree name differs."))

    out.append(Suggestion("low",
        "Keep the layout ATS friendly: one column, standard headings, no text in images or text boxes, and save "
        "as DOCX or a text-based PDF."))

    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(out, key=lambda s: order[s.priority])


def _join(items: list[str]) -> str:
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]
