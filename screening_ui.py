"""Streamlit page: set requirements, import many CVs, get a ranked shortlist."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ats.bulk import load_candidates
from ats.screening import EDU_ORDER, LICENCES, Requirements, evaluate, rank

LEVEL_LABELS = {"Not needed": "off", "Nice to have": "preferred", "Must have": "must"}
ICONS = {"pass": "✅", "fail": "❌", "unknown": "❓", "n/a": "—"}


def _lines(text: str) -> list[str]:
    return [p.strip() for chunk in text.splitlines() for p in chunk.split(",") if p.strip()]


def _picker(label: str, key: str, default: str) -> str:
    choice = st.radio(label, list(LEVEL_LABELS), index=list(LEVEL_LABELS).index(default), horizontal=True, key=key)
    return LEVEL_LABELS[choice]


def requirements_form() -> Requirements:
    r = Requirements()
    tabs = st.tabs(["🎓 Education", "🗓 Years of experience", "💼 Position held", "🪪 Licence", "🎂 Age", "🛠 Skills & qualities"])

    with tabs[0]:
        st.caption("Choose what each qualification type means for this job. **Not needed** types are ignored, so you can accept "
                   "candidates without a degree, a diploma or any other type. **Accepted**: a candidate needs any one of the accepted types. "
                   "**Required**: every candidate must have it.")
        for lvl in EDU_ORDER:
            c1, c2 = st.columns([2, 3])
            c1.write(f"**{lvl}**")
            choice = c2.radio(lvl, ["Not needed", "Accepted", "Required"], horizontal=True, key=f"edu_{lvl}",
                              index=0, label_visibility="collapsed")
            if choice == "Accepted":
                r.education_accepted.append(lvl)
            elif choice == "Required":
                r.education_must.append(lvl)
        if r.education_accepted or r.education_must:
            r.education_level = _picker("How strict is the education requirement?", "edu_level", "Must have")
            r.education_fields = _lines(st.text_area("Fields of study (optional, one per line)", key="edu_fields",
                                                      placeholder="Accounting\nData science", height=90))
        else:
            st.info("Every qualification type is **Not needed**, so education is ignored and nobody is marked down for it.")

    with tabs[1]:
        r.experience_level = _picker("Years of experience", "exp_level", "Must have")
        if r.experience_level != "off":
            c1, c2 = st.columns(2)
            r.min_years = c1.number_input("Minimum years", 0.0, 50.0, 2.0, 0.5, key="exp_min")
            if c2.checkbox("Also set a maximum", key="exp_has_max"):
                r.max_years = c2.number_input("Maximum years", r.min_years, 60.0, max(r.min_years, 10.0), 0.5, key="exp_max")
            st.caption("Years are counted from the dated roles in the experience section (overlaps counted once), or from a line like “5 years experience”.")

    with tabs[2]:
        r.position_level = _picker("Position held", "pos_level", "Not needed")
        if r.position_level != "off":
            r.positions = _lines(st.text_area("Job titles you want (one per line)", key="pos_list",
                                              placeholder="Accountant\nFinance Officer", height=120))
            st.caption("A candidate matches if any of these titles appears in their work experience.")

    with tabs[3]:
        r.licence_level = _picker("Licence or registration", "lic_level", "Not needed")
        if r.licence_level != "off":
            picked = st.multiselect("Common licences", list(LICENCES), key="lic_pick")
            extra = _lines(st.text_input("Other licences (comma separated)", key="lic_extra", placeholder="Class 2, Nursing council"))
            r.licences = picked + extra
            r.licence_all = st.radio("Candidate needs", ["All of them", "Any one of them"], horizontal=True, key="lic_mode") == "All of them"

    with tabs[4]:
        r.age_level = _picker("Age", "age_level", "Not needed")
        if r.age_level != "off":
            c1, c2 = st.columns(2)
            r.age_min = int(c1.number_input("Minimum age", 16, 80, 18, key="age_min"))
            r.age_max = int(c2.number_input("Maximum age", int(r.age_min), 80, max(int(r.age_min), 45), key="age_max"))
            st.caption("Age is read from “Age: 27”, “27 years old” or a date of birth. CVs that do not state it are marked **Check manually**. "
                       "Age limits can be restricted by employment law, so check what applies to you.")

    with tabs[5]:
        r.skills_level = _picker("Skills and qualities", "skill_level", "Nice to have")
        if r.skills_level != "off":
            r.skills = _lines(st.text_area("Skills and qualities (comma or one per line)", key="skills",
                                           placeholder="Excel, Python, communication, teamwork", height=120))
            r.skills_min_pct = st.slider("Candidate must have at least this share of them", 10, 100, 70, 10, key="skills_pct", format="%d%%")
    return r


def import_section() -> None:
    st.subheader("2. Import CVs")
    files = st.file_uploader("Select many CV files at once (PDF, DOCX, TXT), or upload a ZIP with all of them",
                             type=["pdf", "docx", "txt", "md", "zip"], accept_multiple_files=True, key="bulk_files")
    c1, c2, _ = st.columns([1, 1, 3])
    if c1.button("Import CVs", type="primary", disabled=not files):
        bar = st.progress(0.0, text="Reading CVs…")

        def tick(i: int, n: int, name: str) -> None:
            bar.progress(i / max(n, 1), text=f"Reading {i}/{n}: {name.split('/')[-1]}")

        cands, problems = load_candidates([(f.name, f.getvalue()) for f in files], tick)
        st.session_state["cvs"], st.session_state["import_problems"] = cands, problems
        bar.empty()
    if c2.button("Clear imported CVs", disabled="cvs" not in st.session_state):
        st.session_state.pop("cvs", None)
        st.session_state.pop("import_problems", None)
        st.rerun()
    if "cvs" in st.session_state:
        st.success(f"{len(st.session_state['cvs'])} CVs imported and ready to screen.")
    problems = st.session_state.get("import_problems") or []
    if problems:
        with st.expander(f"{len(problems)} files were skipped or had problems"):
            for p in problems:
                st.write("• " + p)


def _cell(check) -> str:
    if check.outcome == "n/a":
        return "— not required"
    return f"{ICONS[check.outcome]} {check.detail}"


def results_section(req: Requirements) -> None:
    st.subheader("3. Ranked results")
    cands = st.session_state.get("cvs") or []
    if not cands:
        st.info("Import your CVs above and the ranked list appears here. Change the requirements at any time and the list updates.")
        return
    results = rank([evaluate(c, req) for c in cands])
    counts = {v: sum(r.verdict == v for r in results) for v in ("Shortlist", "Check manually", "Not shortlisted")}
    m = st.columns(4)
    m[0].metric("CVs screened", len(results))
    m[1].metric("Shortlist", counts["Shortlist"])
    m[2].metric("Check manually", counts["Check manually"])
    m[3].metric("Not shortlisted", counts["Not shortlisted"])
    if all(c.level == "off" for c in results[0].checks):
        st.warning("Every requirement is set to “Not needed”, so all CVs score 100. Switch some requirements to Nice to have or Must have.")

    view = st.radio("Show", ["Everyone", "Shortlist only", "Shortlist + check manually"], horizontal=True, key="view")
    shown = [r for r in results if view == "Everyone" or r.verdict == "Shortlist" or (view.endswith("manually") and r.verdict == "Check manually")]

    rows = []
    for i, r in enumerate(shown, 1):
        by = {c.name: c for c in r.checks}
        rows.append({
            "Rank": i, "Candidate": r.facts.name, "Verdict": r.verdict, "Score": r.score,
            "Failed must-haves": ", ".join(r.failed_musts),
            **{name: _cell(by[name]) for name in ("Education", "Experience", "Position", "Licence", "Age", "Skills")},
            "Email": r.facts.email, "Phone": r.facts.phone, "File": r.facts.filename,
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, width="stretch",
                 column_config={"Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d")})
    st.download_button("Download results (CSV for Excel)", df.to_csv(index=False).encode("utf-8-sig"), "cv_screening_results.csv", "text/csv")

    st.subheader("Look at one candidate")
    if shown:
        pick = st.selectbox("Candidate", [f"{i}. {r.facts.name} ({r.verdict}, {r.score})" for i, r in enumerate(shown, 1)])
        r = shown[int(pick.split(".")[0]) - 1]
        for c in r.checks:
            st.markdown(f"**{c.name}** ({ {'off': 'not needed', 'preferred': 'nice to have', 'must': 'must have'}[c.level] }): {_cell(c)}")
        with st.expander("CV text as read by the scanner"):
            st.text(r.facts.text)


def render() -> None:
    st.header("Screen many CVs against your requirements")
    st.caption("Set what you need, import all the CVs at once, and get a ranked shortlist. Anything you mark “Not needed” is ignored.")
    st.subheader("1. Requirements")
    req = requirements_form()
    st.divider()
    import_section()
    st.divider()
    results_section(req)
