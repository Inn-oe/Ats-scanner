"""ATS CV Scanner. Run locally with:  streamlit run app.py"""

import streamlit as st

import screening_ui
import single_cv

st.set_page_config(page_title="ATS CV Scanner", page_icon="📄", layout="wide")
st.title("📄 ATS CV Scanner")

MODES = ["Screen many CVs (for employers)", "Check one CV against a job"]
mode = st.sidebar.radio("What do you want to do?", MODES)
st.sidebar.caption("Everything runs on this server. CVs are held in memory for your session only and are not saved.")

if mode == MODES[0]:
    screening_ui.render()
else:
    single_cv.render()
