# ATS CV Scanner

Check how well your CV matches a job advert before you apply, the way an Applicant Tracking System (ATS) would.

There are two modes, chosen in the sidebar.

## Mode 1: Screen many CVs (for employers)

Set your requirements, import all your CVs at once (select many files, or upload one ZIP; 100+ is fine), and get a ranked shortlist you can download as CSV for Excel.

Each requirement has its own tab and can be set to **Not needed**, **Nice to have** or **Must have**:

| Tab | What you set |
|---|---|
| Education | Which levels you accept (secondary, certificate / short course, training / apprenticeship, diploma, degree, master's, PhD), plus optional fields of study. Choose **Not needed** if you do not require a degree or any qualification. |
| Years of experience | Minimum, and optionally a maximum. |
| Position held | Job titles you want to see in a candidate's work experience. |
| Licence | Driver's licence, forklift, first aid, professional registrations, or your own. Need all of them or any one. |
| Age | The minimum and maximum age the company wants. |
| Skills & qualities | Your list of skills, with the share a candidate must have. |

A CV that fails any **Must have** is *Not shortlisted*. A CV where a must-have cannot be read (for example no age on the CV) is *Check manually*. Everyone else is *Shortlist*, ranked by a score from the requirements you switched on. Change a requirement and the ranking updates straight away. Open any candidate to see exactly which checks passed or failed.

Notes: age and years of experience are read from the CV text (date of birth, "Age: 27", dated roles). Age limits can be restricted by employment law, so check what applies to you. Imported CVs are kept in memory for your session only.

## Mode 2: Check one CV against a job (for job seekers)

Upload your CV (PDF, DOCX or TXT), paste a job advert or just a list of the qualities you need, and you get:

- **A match score out of 100**, with a breakdown (skills, keywords, overall relevance, education fit, CV structure).
- **Skills found and missing**: technical and soft skills, split into required, nice to have, and either/or options.
- **Keywords** from the advert that your CV does or does not use.
- **CV format checks**: contact details, standard section headings, length, numbers in achievements, action verbs, weak phrases.
- **Prioritised suggestions** telling you exactly what to change for this job.

It runs fully offline. No API keys, and your CV is never stored.

## Run it

```bash
git clone https://github.com/Inn-oe/ats-scanner.git
cd ats-scanner
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501. Click **Try with the sample CV and advert** to see an example report.

### Command line

```bash
python -m ats.cli my_cv.pdf job.txt            # job advert saved in a text file
python -m ats.cli my_cv.docx --job "SQL, Python, Power BI, communication, stakeholder management"
python -m ats.cli my_cv.pdf job.txt --json     # full report as JSON
```

### Live app

Deployed on Render (free plan): https://ats-scanner-qlo8.onrender.com

The free plan sleeps after 15 minutes without visitors, so the first visit after a break can take up to a minute to load. Settings are in [`render.yaml`](render.yaml).

To deploy your own copy instead, use Render's **New > Blueprint** with this repo, or [Streamlit Community Cloud](https://share.streamlit.io) with `app.py` as the main file.

## How the score works

| Part | Weight | What it measures |
|---|---|---|
| Skills match | 45% | Skills from the advert found in your CV. Required skills count double nice-to-haves; technical skills count a bit more than soft skills. |
| Keyword match | 20% | The advert's most repeated words and phrases that are not already skills (e.g. "data analyst", "datasets", "insights"). |
| Overall relevance | 10% | How similar the wording of your CV is to the advert overall. |
| Education fit | 10% | Whether the degree level and subject the advert asks for appear in your CV. |
| CV structure & impact | 15% | Contact details, standard headings, length, quantified achievements, action verbs, no clichés. |

If a part does not apply (for example the advert does not mention a degree), its weight is spread over the others.

A skill counts as **nice to have** when every sentence that mentions it uses words like "desirable", "advantage", "a plus" or "preferred". If the advert says "Python **or** R" and you have Python, R is shown as an **either/or** option and does not lower your score.

## Make it fit your applications

The skills list lives in [`ats/skills.py`](ats/skills.py). It is tuned for data science, data analyst and graduate trainee roles. To add a skill, put it in `CUSTOM_SKILLS` with the words that count as a mention:

```python
CUSTOM_SKILLS = {
    "Alteryx": ["alteryx"],
    "Mobile Money Analytics": ["mobile money", "ecocash"],
}
```

## Limits to know about

- It matches words, not meaning. "Built dashboards in Tableau" will not count as Power BI. That is also how many real ATS filters behave, which is why using the advert's exact words matters.
- Scanned or image-only PDFs have no readable text. If the scanner reads nothing, real ATS systems probably cannot either.
- Multi-column PDF layouts may be read out of order. Expand "See the text the scanner read from your CV" in the app to check.
- The score is a guide for tailoring your CV, not a prediction of whether you will be shortlisted.

## Development

```bash
pip install -r requirements-dev.txt
pytest
```

Project layout:

```
app.py            Streamlit entry point (mode switch)
screening_ui.py   Employer page: requirement tabs, bulk import, ranked results
single_cv.py      Job seeker page: one CV against one job
ats/screening.py  Requirements, CV facts (age, years, education) and shortlist logic
ats/bulk.py       Bulk import of many files or ZIPs
ats/parser.py     Reads text from PDF, DOCX and TXT files
ats/skills.py     Skills taxonomy (edit this to add skills)
ats/analyzer.py   Scoring, matching and suggestions
ats/cli.py        Command line tool
samples/          Example CV and job advert
tests/            pytest tests
```
