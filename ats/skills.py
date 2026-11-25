"""Skills taxonomy used to spot skills in CVs and job adverts.

Each entry maps a canonical skill name to the aliases that count as a mention.
Matching is case-insensitive and on word boundaries. An alias starting with
"cs:" is matched case-sensitively (used for the language "R"). Add your own skills to CUSTOM_SKILLS at the bottom.
"""

TECHNICAL_SKILLS: dict[str, list[str]] = {
    # Programming and querying
    "Python": ["python", "python3"],
    "R": ["r programming", "r studio", "rstudio", "cs:R", "tidyverse", "ggplot2", "dplyr", "r shiny"],
    "SQL": ["sql", "mysql", "postgresql", "postgres", "t-sql", "tsql", "sqlite", "pl/sql", "sql server", "ms sql"],
    "SAS": ["sas"],
    "STATA": ["stata"],
    "SPSS": ["spss"],
    "MATLAB": ["matlab"],
    "Java": ["java"],
    "JavaScript": ["javascript", "js", "typescript", "node.js", "nodejs"],
    "Scala": ["scala"],
    "Julia": ["julia"],
    "VBA": ["vba", "macros"],
    "Bash / Linux": ["bash", "linux", "shell scripting", "unix"],
    # Python data libraries
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
    "TensorFlow": ["tensorflow", "keras"],
    "PyTorch": ["pytorch", "torch"],
    "Matplotlib / Seaborn": ["matplotlib", "seaborn", "plotly"],
    "SciPy / statsmodels": ["scipy", "statsmodels"],
    "NLP": ["nlp", "natural language processing", "text mining", "spacy", "nltk", "transformers", "hugging face"],
    "LLMs / Generative AI": ["llm", "llms", "large language model", "large language models", "generative ai", "genai", "prompt engineering", "rag"],
    # Analytics and BI
    "Excel": ["excel", "ms excel", "microsoft excel", "spreadsheets", "pivot tables", "vlookup", "xlookup", "power query"],
    "Power BI": ["power bi", "powerbi", "dax"],
    "Tableau": ["tableau"],
    "Looker / Looker Studio": ["looker", "looker studio", "google data studio", "data studio"],
    "Qlik": ["qlik", "qlikview", "qlik sense"],
    "Google Analytics": ["google analytics", "ga4"],
    "Data Visualisation": ["data visualisation", "data visualization", "dashboards", "dashboard", "dashboarding", "reporting dashboards"],
    "Data Analysis": ["data analysis", "data analytics", "analytical skills", "analysing data", "analyzing data", "analyse data", "analyze data"],
    "Data Cleaning": ["data cleaning", "data cleansing", "data wrangling", "data preparation", "data quality"],
    "Statistics": ["statistics", "statistical", "statistical analysis", "statistical modelling", "statistical modeling", "statistical methods", "inferential statistics"],
    "Hypothesis Testing / A/B Testing": ["hypothesis testing", "a/b testing", "ab testing", "experimentation", "experimental design"],
    "Regression": ["regression", "linear regression", "logistic regression"],
    "Time Series / Forecasting": ["time series", "forecasting", "arima", "prophet"],
    "Machine Learning": ["machine learning", "ml", "predictive modelling", "predictive modeling", "classification", "clustering", "random forest", "xgboost", "gradient boosting"],
    "Deep Learning": ["deep learning", "neural networks", "neural network", "cnn", "lstm"],
    "Econometrics": ["econometrics", "econometric"],
    "Actuarial / Risk Modelling": ["actuarial", "risk modelling", "risk modeling", "credit risk", "stochastic"],
    # Data engineering and cloud
    "ETL / Data Pipelines": ["etl", "elt", "data pipelines", "data pipeline", "airflow", "dbt", "ssis"],
    "Data Warehousing": ["data warehouse", "data warehousing", "snowflake", "redshift", "bigquery", "synapse", "databricks"],
    "Big Data (Spark/Hadoop)": ["spark", "pyspark", "hadoop", "big data", "hive", "kafka"],
    "NoSQL": ["nosql", "mongodb", "cassandra", "dynamodb"],
    "Data Modelling": ["data modelling", "data modeling", "dimensional modelling", "star schema"],
    "AWS": ["aws", "amazon web services", "s3", "sagemaker", "ec2"],
    "Azure": ["azure", "azure ml"],
    "Google Cloud": ["gcp", "google cloud"],
    "Docker": ["docker", "containers", "kubernetes"],
    "Git / Version Control": ["git", "github", "gitlab", "version control"],
    "APIs": ["api", "apis", "rest api", "fastapi", "flask", "web scraping"],
    "Jupyter": ["jupyter", "jupyter notebook", "notebooks", "google colab"],
    "Streamlit": ["streamlit"],
    # Business and governance
    "Data Governance / GDPR": ["data governance", "gdpr", "data protection", "data privacy"],
    "Business Intelligence": ["business intelligence"],
    "KPIs / Performance Reporting": ["kpi", "kpis", "metrics", "performance reporting", "management information", "mi reporting"],
    "Financial Analysis": ["financial analysis", "financial modelling", "financial modeling", "budgeting", "valuation"],
    "Agile / Scrum": ["agile", "scrum", "kanban", "jira"],
    "Microsoft Office": ["microsoft office", "ms office", "ms word", "microsoft word", "powerpoint", "office 365", "microsoft 365"],
    "Project Management": ["project management", "project planning", "prince2", "pmp"],
}

SOFT_SKILLS: dict[str, list[str]] = {
    "Communication": ["communication", "communicate", "communicating", "written and verbal", "verbal and written", "presentation skills", "presenting"],
    "Teamwork": ["teamwork", "team player", "collaboration", "collaborative", "collaborate", "work in a team", "working in a team", "cross-functional"],
    "Problem Solving": ["problem solving", "problem-solving", "solve problems", "solving problems", "troubleshooting"],
    "Critical Thinking": ["critical thinking", "analytical thinking", "logical thinking"],
    "Attention to Detail": ["attention to detail", "detail oriented", "detail-oriented", "meticulous"],
    "Time Management": ["time management", "prioritise", "prioritize", "prioritisation", "prioritization", "meet deadlines", "meeting deadlines", "deadline driven"],
    "Leadership": ["leadership", "led a team", "team lead", "mentoring", "mentored"],
    "Stakeholder Management": ["stakeholder management", "stakeholders", "stakeholder engagement", "client facing", "client-facing"],
    "Adaptability": ["adaptability", "adaptable", "flexible", "flexibility", "fast-paced", "fast paced"],
    "Curiosity / Willingness to Learn": ["curious", "curiosity", "eager to learn", "willingness to learn", "keen to learn", "growth mindset", "learn quickly", "quick learner"],
    "Initiative": ["initiative", "self-motivated", "self motivated", "proactive", "self-starter", "self starter", "independently"],
    "Storytelling with Data": ["storytelling", "data storytelling", "insights to non-technical", "non-technical audiences", "non-technical stakeholders"],
    "Commercial Awareness": ["commercial awareness", "business acumen", "commercially aware"],
    "Numeracy": ["numeracy", "numerate", "numerical skills", "quantitative skills", "strong numerical"],
    "Research": ["research", "research skills", "literature review"],
    "Customer Focus": ["customer focus", "customer service", "customer-focused", "client service"],
}

EDUCATION_TERMS: dict[str, list[str]] = {
    "Degree (Bachelor's)": ["bachelor", "bachelors", "bachelor's", "bsc", "b.sc", "ba", "undergraduate degree", "degree", "honours", "hons", "2:1", "2.1", "upper second"],
    "Master's": ["master", "masters", "master's", "msc", "m.sc", "mba", "postgraduate"],
    "PhD": ["phd", "ph.d", "doctorate"],
}

DEGREE_SUBJECTS = [
    "data science", "statistics", "mathematics", "maths", "computer science", "economics",
    "actuarial science", "physics", "engineering", "finance", "accounting", "business analytics",
    "operations research", "information systems", "information technology", "stem", "quantitative",
]

# Add skills that are specific to the roles you apply for here.
CUSTOM_SKILLS: dict[str, list[str]] = {}


def all_skills() -> dict[str, dict[str, list[str]]]:
    technical = {**TECHNICAL_SKILLS, **CUSTOM_SKILLS}
    return {"technical": technical, "soft": SOFT_SKILLS}
