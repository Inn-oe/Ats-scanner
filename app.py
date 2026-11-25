"""Streamlit web app for the ATS scanner.

Run locally with:  streamlit run app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from ats import analyze, extract_text
from ats.parser import UnsupportedFileError

SAMPLES = Path(__file__).parent / "samples"

st.set_page_config(page_title="ATS CV Scanner", page_icon="📄", layout="wide")
st.title("📄 ATS CV Scanner")
st.caption(
    "Upload your CV and paste a job advert (or just the qualities you want to match). "
    "You get a match score, the skills and keywords found and missing, and concrete fixes. "
    "Everything runs on this server; nothing is stored."
)

left, right = st.columns(2)
with left:
    st.subheader("1. Your CV")
    upload = st.file_uploader("Upload CV (PDF, DOCX or TXT)", type=["pdf", "docx", "txt", "md"])
    pasted_cv = st.text_area("…or paste your CV text", height=220, placeholder="Paste the text of your CV here")
with right:
    st.subheader("2. The job")
    job_text = st.text_area(
        "Paste the job advert, or list the skills and qualities you need",
        height=330,
        placeholder="e.g. Graduate Data Analyst. Requirements: SQL, Python, Power BI, strong communication…",
    )

c1, c2 = st.columns([1, 4])
run = c1.button("Scan my CV", type="primary", use_container_width=True)
if c2.button("Try with the sample CV and advert"):
    st.session_state["use_sample"] = True
    run = True

if not run:
    st.stop()

cv_text = ""
if st.session_state.pop("use_sample", False):
    cv_text = (SAMPLES / "sample_cv.txt").read_text()
    job_text = (SAMPLES / "job_data_analyst_graduate.txt").read_text()
elif upload is not None:
    try:
        cv_text = extract_text(upload.getvalue(), upload.name)
    except UnsupportedFileError as e:
        st.error(str(e))
        st.stop()
    except Exception as e:  # noqa: BLE001 - show any parse error to the user
        st.error(f"Could not read that file: {e}")
        st.stop()
else:
    cv_text = pasted_cv

if len(cv_text.strip()) < 50:
    st.error(
        "Could not find enough text in the CV. If you uploaded a scanned or image-only PDF, "
        "an ATS cannot read it either. Export it again as a text-based PDF or DOCX."
    )
    st.stop()
if not job_text.strip():
    st.error("Paste the job advert or the list of qualities you want to match.")
    st.stop()

result = analyze(cv_text, job_text)

# ---- Score -------------------------------------------------------------------
st.divider()
s1, s2 = st.columns([1, 3])
s1.metric("ATS match score", f"{result.score}/100")
s1.progress(result.score / 100)
with s2:
    st.markdown(f"### {result.verdict}")
    for name, value in result.breakdown.items():
        st.write(f"**{name}**: {value}%")
        st.progress(value / 100)

# ---- Skills ------------------------------------------------------------------
st.divider()
st.subheader("Skills from the advert")
k1, k2 = st.columns(2)
with k1:
    st.markdown("#### ✅ Found in your CV")
    for s in result.matched_skills:
        tag = "" if s.importance == "required" else " · nice to have"
        st.markdown(f"- **{s.name}** ({s.category}{tag}, mentioned {s.cv_mentions}×)")
    if not result.matched_skills:
        st.write("None yet.")
with k2:
    st.markdown("#### ❌ Missing from your CV")
    for s in result.missing_skills:
        tag = {"required": "", "desirable": " · nice to have", "alternative": " · either/or, you have another option"}[s.importance]
        st.markdown(f"- **{s.name}** ({s.category}{tag})")
    if not result.missing_skills:
        st.write("Nothing missing. 🎉")

st.subheader("Other keywords in the advert")
w1, w2 = st.columns(2)
w1.markdown("**Found:** " + (", ".join(f"`{k}`" for k in result.keywords_found) or "none"))
w2.markdown("**Missing:** " + (", ".join(f"`{k}`" for k in result.keywords_missing) or "none"))
if result.extra_cv_skills:
    st.caption("Skills on your CV that this advert does not ask for: " + ", ".join(result.extra_cv_skills))

# ---- Suggestions -------------------------------------------------------------
st.divider()
st.subheader("How to improve this CV for this job")
icons = {"high": "🔴", "medium": "🟠", "low": "🟢"}
for s in result.suggestions:
    st.markdown(f"{icons[s.priority]} **{s.priority.capitalize()}**: {s.text}")

# ---- Checks ------------------------------------------------------------------
st.divider()
st.subheader("CV format checks")
cols = st.columns(2)
for i, (name, ok) in enumerate(result.checks.items()):
    cols[i % 2].write(("✅ " if ok else "❌ ") + name)
st.caption(
    f"{result.stats['word_count']} words · {result.stats['quantified_lines']} lines with numbers · "
    f"{result.stats['action_verb_lines']} lines starting with action verbs"
)

with st.expander("See the text the scanner read from your CV"):
    st.text(cv_text)

st.download_button(
    "Download full report (JSON)",
    data=json.dumps(result.to_dict(), indent=2),
    file_name="ats_report.json",
    mime="application/json",
)
