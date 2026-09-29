import streamlit as st
import pandas as pd
import altair as alt
import re
import sqlite3
import hashlib
from difflib import SequenceMatcher
from collections import Counter
from pathlib import Path
from datetime import datetime

# =========================================================
# PATENT-ALIGNED CAREER & SKILL GAP ADVISOR
# =========================================================
# This prototype follows the workflow described in the supplied
# Invention Disclosure Form:
# Student Profile -> Assessment -> Structured Skill Profile ->
# Career Matching -> Skill-Gap Analysis -> Gap Prioritization ->
# Personalized Learning Roadmap -> Reassessment/Profile Update.
#
# The implementation is a software prototype; it does not by itself
# establish patentability, novelty, or legal scope.
# =========================================================

st.set_page_config(
    page_title="AI Personalized Career & Skill Gap Advisor",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_PATH = "users.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("SELECT id FROM users WHERE username = 'demo'")
    if not c.fetchone():
        demo_hash = hashlib.sha256("demo123".encode()).hexdigest()
        c.execute(
            "INSERT INTO users (username, full_name, email, password_hash) VALUES (?, ?, ?, ?)",
            ("demo", "Demo Student", "demo@careeradvisor.ai", demo_hash)
        )
    conn.commit()
    conn.close()

init_db()

def authenticate_user(username, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    pwd_hash = hashlib.sha256(password.strip().encode()).hexdigest()
    c.execute(
        "SELECT username, full_name, email FROM users "
        "WHERE LOWER(username)=LOWER(?) AND password_hash=?",
        (username.strip(), pwd_hash)
    )
    row = c.fetchone()
    conn.close()
    if row:
        return {"username": row[0], "full_name": row[1], "email": row[2]}
    return None

def register_user(username, full_name, email, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    pwd_hash = hashlib.sha256(password.strip().encode()).hexdigest()
    try:
        c.execute(
            "INSERT INTO users (username, full_name, email, password_hash) VALUES (?, ?, ?, ?)",
            (username.strip().lower(), full_name.strip(), email.strip(), pwd_hash)
        )
        conn.commit()
        conn.close()
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        conn.close()
        return False, "This username already exists."
    except Exception as exc:
        conn.close()
        return False, f"Error creating account: {exc}"

# =========================================================
# SESSION STATE
# =========================================================
DEFAULTS = {
    "authenticated": False,
    "user": None,
    "analysis_done": False,
    "student_profile": {},
    "student_skills": [],
    "results": [],
    "reassessment_history": [],
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value.copy() if isinstance(value, dict) else list(value) if isinstance(value, list) else value

if "skill_input_text" not in st.session_state:
    st.session_state.skill_input_text = "Python, SQL, Git, DSA, Machine Learning"

if "project_skills_text" not in st.session_state:
    st.session_state.project_skills_text = ""

if "certification_skills_text" not in st.session_state:
    st.session_state.certification_skills_text = ""

if "assessment_skills_text" not in st.session_state:
    st.session_state.assessment_skills_text = ""

# =========================================================
# UI STYLE
# =========================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 3rem;
        max-width: 1300px;
    }

    /* Hero Banner */
    .hero-banner {
        background: linear-gradient(135deg, #1E1E38 0%, #2D1B69 50%, #141E30 100%);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 18px;
        padding: 2.2rem 2.5rem;
        margin-bottom: 1.8rem;
        box-shadow: 0 12px 35px rgba(0, 0, 0, 0.25);
        color: #FFFFFF;
        position: relative;
        overflow: hidden;
    }
    .hero-banner::after {
        content: '';
        position: absolute;
        top: -40px;
        right: -40px;
        width: 180px;
        height: 180px;
        background: radial-gradient(circle, rgba(99, 102, 241, 0.35) 0%, rgba(0,0,0,0) 70%);
        border-radius: 50%;
        pointer-events: none;
    }
    .hero-title {
        font-size: 2.25rem;
        font-weight: 800;
        background: linear-gradient(90deg, #FFFFFF 0%, #E0E7FF 50%, #A5B4FC 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
        letter-spacing: -0.02em;
    }
    .hero-subtitle {
        font-size: 1.05rem;
        color: #C7D2FE;
        max-width: 820px;
        line-height: 1.55;
        margin-bottom: 1.1rem;
    }
    .hero-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 0.6rem;
    }
    .hero-tag {
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 999px;
        padding: 0.3rem 0.85rem;
        font-size: 0.82rem;
        font-weight: 600;
        color: #EEF2FF;
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
    }

    /* Metric Cards */
    .metric-card {
        background: linear-gradient(145deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 1.2rem 1.4rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        height: 100%;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: rgba(99, 102, 241, 0.4);
    }
    .metric-title {
        font-size: 0.82rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94A3B8;
        margin-bottom: 0.4rem;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 800;
        color: #F8FAFC;
        line-height: 1.2;
    }
    .metric-sub {
        font-size: 0.82rem;
        color: #A5B4FC;
        margin-top: 0.35rem;
    }

    /* Badges */
    .skill-badge {
        display: inline-block;
        padding: 0.22rem 0.65rem;
        border-radius: 8px;
        font-size: 0.8rem;
        font-weight: 600;
        margin: 0.2rem 0.25rem 0.2rem 0;
        white-space: nowrap;
    }
    .badge-strong {
        background: rgba(16, 185, 129, 0.15);
        color: #34D399;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .badge-partial {
        background: rgba(245, 158, 11, 0.15);
        color: #FBBF24;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }
    .badge-missing {
        background: rgba(239, 68, 68, 0.12);
        color: #F87171;
        border: 1px solid rgba(239, 68, 68, 0.25);
    }
    .badge-priority {
        font-size: 0.7rem;
        padding: 0.1rem 0.4rem;
        border-radius: 4px;
        margin-left: 0.3rem;
        font-weight: 700;
        text-transform: uppercase;
    }
    .pri-high { background: #DC2626; color: white; }
    .pri-med { background: #D97706; color: white; }
    .pri-low { background: #475569; color: white; }

    /* Match Pill in Career Titles */
    .match-pill {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 999px;
        font-weight: 700;
        font-size: 0.85rem;
    }
    .match-green { background: #059669; color: #FFFFFF; }
    .match-amber { background: #D97706; color: #FFFFFF; }
    .match-red { background: #DC2626; color: #FFFFFF; }

    /* Top Career Spotlight Card */
    .spotlight-card {
        background: linear-gradient(135deg, rgba(30, 27, 75, 0.6) 0%, rgba(49, 46, 129, 0.3) 100%);
        border: 1px solid rgba(129, 140, 248, 0.3);
        border-radius: 16px;
        padding: 1.4rem 1.6rem;
        margin-bottom: 1rem;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.2);
    }

    /* Auth Form & Container Styling */
    div[data-testid="stForm"] {
        border: none !important;
        padding: 0.5rem 0.2rem !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: linear-gradient(165deg, rgba(30, 27, 75, 0.75) 0%, rgba(15, 23, 42, 0.95) 100%) !important;
        border: 1px solid rgba(129, 140, 248, 0.35) !important;
        border-radius: 20px !important;
        padding: 1.6rem 2rem !important;
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.4), 0 0 35px rgba(99, 102, 241, 0.15) !important;
    }
    .auth-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.2) 0%, rgba(168, 85, 247, 0.2) 100%);
        border: 1px solid rgba(165, 180, 252, 0.35);
        padding: 0.35rem 0.95rem;
        border-radius: 999px;
        color: #C7D2FE;
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        margin-bottom: 0.7rem;
    }
    .auth-tag {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        font-size: 0.76rem;
        font-weight: 600;
        color: #A5B4FC;
        background: rgba(99, 102, 241, 0.12);
        border: 1px solid rgba(99, 102, 241, 0.25);
        padding: 0.22rem 0.6rem;
        border-radius: 999px;
        margin: 0.15rem 0.25rem;
    }

    div[data-testid="stButton"] > button {
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.2s ease;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0px 0px;
        padding: 8px 16px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

ALIASES = {
    # Programming Languages
    "js": "javascript",
    "javascript": "javascript",
    "ts": "typescript",
    "typescript": "typescript",
    "py": "python",
    "python": "python",
    "python3": "python",
    "c++": "c++",
    "cpp": "c++",
    "c#": "c#",
    "csharp": "c#",
    "cs": "c#",
    "golang": "go",
    "go": "go",
    "go lang": "go",
    "rust": "rust",
    "rs": "rust",
    "kotlin": "kotlin",
    "kt": "kotlin",
    "swift": "swift",
    "dart": "dart",
    "java": "java",
    "c": "c",
    "solidity": "solidity",
    "sol": "solidity",
    "bash": "bash scripting",
    "shell": "bash scripting",
    "shell scripting": "bash scripting",
    "bash scripting": "bash scripting",
    "powershell": "powershell",

    # Web & Fullstack Frameworks
    "html": "html",
    "html5": "html",
    "css": "css",
    "css3": "css",
    "tailwind": "tailwind css",
    "tailwind css": "tailwind css",
    "tailwindcss": "tailwind css",
    "bootstrap": "bootstrap",
    "react": "react",
    "reactjs": "react",
    "react.js": "react",
    "next": "next.js",
    "nextjs": "next.js",
    "next.js": "next.js",
    "vue": "vue",
    "vuejs": "vue",
    "vue.js": "vue",
    "angular": "angular",
    "angularjs": "angular",
    "node": "node.js",
    "nodejs": "node.js",
    "node.js": "node.js",
    "express": "express.js",
    "expressjs": "express.js",
    "express.js": "express.js",
    "django": "django",
    "fastapi": "fastapi",
    "fast-api": "fastapi",
    "spring": "spring boot",
    "spring boot": "spring boot",
    "springboot": "spring boot",
    "hibernate": "hibernate",
    "rest api": "rest api",
    "rest": "rest api",
    "api": "rest api",
    "apis": "rest api",
    "restful": "rest api",
    "graphql": "graphql",
    "grpc": "grpc",
    "microservices": "microservices",
    "oauth": "oauth",

    # Mobile Development
    "flutter": "flutter",
    "react native": "react native",
    "reactnative": "react native",
    "android": "android sdk",
    "android sdk": "android sdk",
    "jetpack compose": "jetpack compose",
    "jetpack": "jetpack compose",
    "ios": "ios sdk",
    "ios sdk": "ios sdk",
    "swiftui": "swiftui",
    "xcode": "xcode",
    "mobile development": "mobile development",

    # Databases & Storage
    "sql": "sql",
    "mysql": "sql",
    "postgresql": "postgresql",
    "postgres": "postgresql",
    "mongodb": "mongodb",
    "mongo": "mongodb",
    "redis": "redis",
    "database": "database",
    "data warehousing": "data warehousing",
    "data modeling": "data modeling",

    # AI, ML, Data Science
    "ml": "machine learning",
    "machine learning": "machine learning",
    "machinelearning": "machine learning",
    "dl": "deep learning",
    "deep learning": "deep learning",
    "deeplearning": "deep learning",
    "ai": "ai",
    "artificial intelligence": "ai",
    "genai": "generative ai",
    "generative ai": "generative ai",
    "llm": "llm",
    "llms": "llm",
    "large language models": "llm",
    "rag": "rag",
    "langchain": "langchain",
    "vector database": "vector database",
    "vector db": "vector database",
    "prompt engineering": "prompt engineering",
    "nlp": "nlp",
    "cv": "computer vision",
    "computer vision": "computer vision",
    "computervision": "computer vision",
    "opencv": "opencv",
    "yolo": "yolo",
    "transformers": "transformers",
    "huggingface": "huggingface",
    "pytorch": "pytorch",
    "torch": "pytorch",
    "tensorflow": "tensorflow",
    "tf": "tensorflow",
    "neural networks": "neural networks",
    "scikit-learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "pandas": "pandas",
    "numpy": "numpy",
    "statistics": "statistics",
    "stats": "statistics",
    "data visualization": "data visualization",
    "power bi": "power bi",
    "powerbi": "power bi",
    "pbi": "power bi",
    "tableau": "tableau",
    "excel": "excel",
    "ms excel": "excel",
    "etl": "etl",
    "spark": "apache spark",
    "apache spark": "apache spark",
    "kafka": "kafka",
    "airflow": "airflow",
    "mlops": "mlops",
    "mlflow": "mlflow",
    "dax": "dax",
    "hadoop": "hadoop",
    "bigquery": "bigquery",

    # Cloud & DevOps
    "aws": "aws",
    "amazon web services": "aws",
    "azure": "azure",
    "microsoft azure": "azure",
    "gcp": "gcp",
    "google cloud": "gcp",
    "cloud": "cloud",
    "cloud architecture": "cloud architecture",
    "docker": "docker",
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    "ci/cd": "ci/cd",
    "cicd": "ci/cd",
    "ci cd": "ci/cd",
    "terraform": "terraform",
    "ansible": "ansible",
    "git": "git",
    "github": "git",
    "gitlab": "git",
    "linux": "linux",
    "ubuntu": "linux",
    "monitoring": "monitoring",
    "prometheus": "prometheus",
    "grafana": "grafana",
    "helm": "helm",
    "sre": "site reliability engineering",

    # Cybersecurity & InfoSec
    "cybersecurity": "cybersecurity",
    "cyber security": "cybersecurity",
    "infosec": "cybersecurity",
    "networking": "networking",
    "tcp/ip": "tcp/ip",
    "wireshark": "wireshark",
    "siem": "siem",
    "splunk": "splunk",
    "burp suite": "burp suite",
    "burp": "burp suite",
    "metasploit": "metasploit",
    "ethical hacking": "ethical hacking",
    "penetration testing": "penetration testing",
    "pentesting": "penetration testing",
    "owasp": "owasp",
    "cloud security": "cloud security",
    "iam": "iam",
    "incident response": "incident response",
    "forensics": "forensics",
    "malware analysis": "malware analysis",
    "cryptography": "cryptography",
    "web security": "web security",

    # Quality Assurance & Testing
    "selenium": "selenium",
    "cypress": "cypress",
    "playwright": "playwright",
    "pytest": "pytest",
    "postman": "postman",
    "jmeter": "jmeter",
    "test automation": "test automation",
    "manual testing": "manual testing",
    "api testing": "api testing",
    "performance testing": "performance testing",

    # Core Engineering & Embedded
    "dsa": "dsa",
    "data structures": "dsa",
    "algorithms": "dsa",
    "oop": "oop",
    "system design": "system design",
    "multithreading": "multithreading",
    "low latency": "low latency",
    "memory management": "memory management",
    "embedded systems": "embedded systems",
    "microcontrollers": "microcontrollers",
    "rtos": "rtos",
    "firmware": "firmware",
    "iot": "iot",
    "mqtt": "mqtt",
    "ros": "ros",
    "robotics": "robotics",

    # Game Dev & AR/VR
    "unity": "unity",
    "unreal engine": "unreal engine",
    "unreal": "unreal engine",
    "game development": "game development",
    "ar/vr": "ar/vr",
    "3d math": "3d math",

    # Blockchain
    "blockchain": "blockchain",
    "smart contracts": "smart contracts",
    "ethereum": "ethereum",
    "web3": "web3.js",
    "web3.js": "web3.js",
    "hardhat": "hardhat",

    # Product & Design
    "figma": "figma",
    "ui design": "ui design",
    "ux design": "ux design",
    "wireframing": "wireframing",
    "prototyping": "prototyping",
    "design systems": "design systems",
    "product management": "product management",
    "agile": "agile",
    "scrum": "scrum",
    "jira": "jira",
    "technical writing": "technical writing",
    "documentation": "documentation"
}

def normalize_skill(skill):
    skill = str(skill).lower().strip()
    skill = re.sub(r"\s+", " ", skill)
    if skill in ALIASES:
        return ALIASES[skill]
    compact = skill.replace(" ", "").replace("-", "").replace(".", "")
    if compact in ALIASES:
        return ALIASES[compact]
    return skill

def parse_skill_text(value):
    if not value:
        return []
    parts = re.split(r"[,;\n]+", str(value))
    return [normalize_skill(x) for x in parts if x.strip()]

def similarity(a, b):
    a = normalize_skill(a)
    b = normalize_skill(b)
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.90
    return SequenceMatcher(None, a, b).ratio()

def best_similarity(required_skill, supplied_skills):
    if not supplied_skills:
        return 0.0
    return max(similarity(required_skill, s) for s in supplied_skills)

# =========================================================
# DEPENDENCY GRAPH
# =========================================================
DEPENDENCIES = {
    "css": ["html"],
    "javascript": ["html", "css"],
    "typescript": ["javascript"],
    "tailwind css": ["css"],
    "react": ["javascript", "html", "css"],
    "next.js": ["react", "javascript"],
    "node.js": ["javascript"],
    "express.js": ["node.js"],
    "fastapi": ["python", "rest api"],
    "django": ["python", "sql"],
    "spring boot": ["java", "oop", "sql"],
    "microservices": ["rest api", "docker", "system design"],
    "kotlin": ["java", "oop"],
    "android sdk": ["kotlin", "java"],
    "jetpack compose": ["kotlin", "android sdk"],
    "swift": ["oop"],
    "ios sdk": ["swift"],
    "swiftui": ["swift", "ios sdk"],
    "flutter": ["dart"],
    "react native": ["react", "javascript"],
    "pandas": ["python"],
    "numpy": ["python"],
    "statistics": ["mathematics"],
    "machine learning": ["python", "statistics", "numpy", "pandas"],
    "deep learning": ["python", "machine learning", "mathematics"],
    "pytorch": ["python", "deep learning"],
    "tensorflow": ["python", "deep learning"],
    "computer vision": ["python", "machine learning", "opencv"],
    "nlp": ["python", "machine learning"],
    "transformers": ["python", "deep learning", "nlp"],
    "llm": ["python", "machine learning", "deep learning"],
    "rag": ["python", "llm", "vector database"],
    "langchain": ["python", "llm"],
    "mlops": ["machine learning", "docker", "ci/cd"],
    "docker": ["linux"],
    "kubernetes": ["docker", "linux", "networking"],
    "terraform": ["cloud", "networking"],
    "ci/cd": ["git", "linux"],
    "cybersecurity": ["networking", "linux"],
    "ethical hacking": ["networking", "linux", "web security"],
    "penetration testing": ["networking", "linux", "cybersecurity"],
    "burp suite": ["web security", "networking"],
    "siem": ["networking", "linux", "cybersecurity"],
    "solidity": ["javascript", "blockchain"],
    "smart contracts": ["solidity", "blockchain"],
    "unity": ["c#", "game development"],
    "unreal engine": ["c++", "game development"],
    "power bi": ["sql", "data visualization"],
    "tableau": ["sql", "data visualization"],
    "embedded systems": ["c", "microcontrollers"],
    "firmware": ["c", "embedded systems"],
    "system design": ["dsa", "oop", "database"]
}

def dependency_score(skill, student_skills):
    skill = normalize_skill(skill)
    prereqs = DEPENDENCIES.get(skill, [])
    if not prereqs:
        return 1.0, []
    missing = []
    covered = 0.0
    for prereq in prereqs:
        score = best_similarity(prereq, student_skills)
        if score >= 0.80:
            covered += 1
        elif score >= 0.62:
            covered += 0.5
        else:
            missing.append(prereq)
    return covered / len(prereqs), missing

# =========================================================
# CAREER DATA
# =========================================================
FALLBACK_CAREERS = [
    ("Software Developer", "Software Development", "python:3;dsa:3;oop:2;git:1;sql:2;rest api:2"),
    ("Full Stack Developer", "Web Development", "html:1;css:1;javascript:3;react:3;node.js:2;sql:2;git:1;rest api:2"),
    ("Data Scientist", "Data Science", "python:3;sql:2;statistics:3;pandas:2;numpy:2;machine learning:3;data visualization:1"),
    ("ML Engineer", "AI / Machine Learning", "python:3;machine learning:3;deep learning:3;pytorch:2;docker:1;git:1"),
    ("AI / LLM Engineer", "AI / Machine Learning", "python:3;machine learning:3;deep learning:2;llm:3;langchain:2;rag:3;vector database:2"),
    ("Cloud / DevOps Engineer", "Cloud & DevOps", "linux:2;git:1;docker:3;kubernetes:3;aws:3;ci/cd:2;terraform:2;networking:2"),
    ("Cybersecurity Analyst", "Cybersecurity", "networking:3;linux:2;cybersecurity:3;wireshark:2;siem:2;owasp:2;python:1"),
    ("QA Automation Engineer", "Testing & QA", "python:2;selenium:3;pytest:2;api testing:2;git:1;sql:1"),
    ("UI/UX Designer", "Design", "figma:3;ui design:3;ux design:3;wireframing:2;prototyping:2;design systems:1"),
]

@st.cache_data
def load_careers():
    path = Path("careers.csv")
    rows = []
    if path.exists():
        try:
            df = pd.read_csv(path)
            for _, row in df.iterrows():
                raw = str(row.get("skills", ""))
                skills = []
                for part in raw.split(";"):
                    if ":" not in part:
                        continue
                    skill, weight = part.rsplit(":", 1)
                    try:
                        weight = int(float(weight))
                    except ValueError:
                        weight = 1
                    skills.append({
                        "name": normalize_skill(skill),
                        "original_name": skill.strip(),
                        "weight": max(1, min(5, weight)),
                    })
                if skills:
                    rows.append({
                        "career": str(row.get("career", "Career")).strip(),
                        "category": str(row.get("category", "General")).strip(),
                        "skills": skills,
                        "communication_weight": float(row.get("communication_weight", 10) or 10),
                        "practical_weight": float(row.get("practical_weight", 15) or 15),
                        "academic_weight": float(row.get("academic_weight", 5) or 5),
                    })
        except Exception:
            rows = []

    if not rows:
        for career, category, raw in FALLBACK_CAREERS:
            skills = []
            for part in raw.split(";"):
                skill, weight = part.rsplit(":", 1)
                skills.append({
                    "name": normalize_skill(skill),
                    "original_name": skill.strip(),
                    "weight": int(weight),
                })
            rows.append({
                "career": career,
                "category": category,
                "skills": skills,
                "communication_weight": 10,
                "practical_weight": 15,
                "academic_weight": 5,
            })
    return rows

# =========================================================
# EVIDENCE-BASED STUDENT PROFILE
# =========================================================
EVIDENCE_WEIGHTS = {
    "self_declared": 0.55,
    "assessment": 0.85,
    "project": 0.90,
    "certification": 0.95,
    "academic": 0.70,
}

def build_evidence_map(profile):
    """
    Multi-source skill evidence:
    self-declared + technical assessment + projects + certifications.
    """
    evidence = {}
    source_labels = {}
    source_sets = [
        ("self_declared", profile.get("skills", [])),
        ("project", profile.get("project_skills", [])),
        ("certification", profile.get("certification_skills", [])),
        ("assessment", profile.get("assessment_skills", [])),
    ]

    for source, skills in source_sets:
        for skill in skills:
            skill = normalize_skill(skill)
            if not skill:
                continue
            weight = EVIDENCE_WEIGHTS[source]
            if source == "assessment":
                weight *= max(0.0, min(1.0, float(profile.get("technical_assessment", 0)) / 100.0))
            evidence.setdefault(skill, [])
            source_labels.setdefault(skill, [])
            evidence[skill].append(weight)
            if source not in source_labels[skill]:
                source_labels[skill].append(source.replace("_", " ").title())

    combined = {}
    for skill, weights in evidence.items():
        confidence = 1.0
        for w in weights:
            confidence *= (1.0 - w)
        combined[skill] = 1.0 - confidence

    return combined, source_labels

def evidence_for_skill(required_skill, evidence_map):
    if not evidence_map:
        return 0.0
    best = 0.0
    for skill, confidence in evidence_map.items():
        sim = similarity(required_skill, skill)
        best = max(best, confidence * sim)
    return min(best, 1.0)

def skill_status(confidence):
    if confidence >= 0.75:
        return "strong"
    if confidence >= 0.45:
        return "partial"
    return "missing"

def academic_readiness(cgpa, max_cgpa=10.0):
    try:
        return max(0.0, min(100.0, float(cgpa) / max_cgpa * 100.0))
    except Exception:
        return 0.0

def communication_readiness(communication, grammar):
    return max(0.0, min(100.0, (float(communication) * 0.6) + (float(grammar) * 0.4)))

def practical_evidence_score(career, profile, evidence_map):
    required = career.get("skills", [])
    if not required:
        return 0.0
    project_skills = profile.get("project_skills", [])
    cert_skills = profile.get("certification_skills", [])
    project_hits = 0.0
    cert_hits = 0.0
    total = sum(x["weight"] for x in required) or 1
    for item in required:
        if best_similarity(item["name"], project_skills) >= 0.80:
            project_hits += item["weight"]
        if best_similarity(item["name"], cert_skills) >= 0.80:
            cert_hits += item["weight"]
    # Projects are treated as the primary practical evidence.
    return min(100.0, ((project_hits / total) * 85.0) + ((cert_hits / total) * 15.0))

def analyze_career(career, profile):
    evidence_map, raw_evidence = build_evidence_map(profile)

    total_weight = sum(x["weight"] for x in career["skills"]) or 1
    earned_weight = 0.0
    strong, partial, missing = [], [], []

    for item in career["skills"]:
        conf = evidence_for_skill(item["name"], evidence_map)
        status = skill_status(conf)
        contribution = item["weight"] * conf

        if status == "strong":
            strong.append({
                "skill": item["original_name"],
                "weight": item["weight"],
                "confidence": conf,
                "evidence": raw_evidence.get(normalize_skill(item["name"]), []),
            })
        elif status == "partial":
            partial.append({
                "skill": item["original_name"],
                "weight": item["weight"],
                "confidence": conf,
            })
        else:
            missing.append({
                "skill": item["original_name"],
                "weight": item["weight"],
                "confidence": conf,
            })

        earned_weight += contribution

    skill_coverage_pct = (earned_weight / total_weight) * 100.0
    # Technical assessment is an explicit assessment input in the patent workflow.
    technical_pct = (skill_coverage_pct * 0.75) + (float(profile.get("technical_assessment", 0)) * 0.25)
    practical_pct = practical_evidence_score(career, profile, evidence_map)
    communication_pct = communication_readiness(
        profile.get("communication_score", 0),
        profile.get("grammar_score", 0)
    )
    academic_pct = academic_readiness(profile.get("cgpa", 0))

    # Career requirement mapping is represented by a weighted combination of
    # technical, practical, communication and academic components.
    # These weights can be changed per career through careers.csv columns.
    cw = career.get("communication_weight", 10.0)
    pw = career.get("practical_weight", 15.0)
    aw = career.get("academic_weight", 5.0)
    tw = max(1.0, 100.0 - cw - pw - aw)

    overall = (
        technical_pct * (tw / 100.0)
        + practical_pct * (pw / 100.0)
        + communication_pct * (cw / 100.0)
        + academic_pct * (aw / 100.0)
    )

    missing.sort(key=lambda x: (-x["weight"], x["confidence"]))

    return {
        "career": career["career"],
        "category": career["category"],
        "percentage": overall,
        "technical_pct": technical_pct,
        "practical_pct": practical_pct,
        "communication_pct": communication_pct,
        "academic_pct": academic_pct,
        "strong": strong,
        "partial": partial,
        "missing": missing,
        "total_skills": len(career["skills"]),
        "evidence_map": evidence_map,
    }

def what_if_analysis(career, profile, new_skill):
    before = analyze_career(career, profile)
    simulated = dict(profile)
    simulated["skills"] = list(profile.get("skills", []))
    simulated["skills"].append(normalize_skill(new_skill))
    after = analyze_career(career, simulated)
    readiness, missing_prereqs = dependency_score(new_skill, profile.get("skills", []))
    return {
        "before": before["percentage"],
        "after": after["percentage"],
        "improvement": after["percentage"] - before["percentage"],
        "readiness": readiness,
        "missing_prereqs": missing_prereqs,
    }

def generate_roadmap(career_result, profile):
    roadmap = []
    student_skills = profile.get("skills", [])
    for item in career_result["missing"]:
        skill = item["skill"]
        _, missing_prereqs = dependency_score(skill, student_skills)
        roadmap.append({
            "skill": skill,
            "weight": item["weight"],
            "confidence": item["confidence"],
            "before": missing_prereqs,
        })
    roadmap.sort(key=lambda x: (len(x["before"]), -x["weight"], x["confidence"]))
    return roadmap

# =========================================================
# AUTH PAGE
# =========================================================
def render_auth_page():
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown("""
        <div style="text-align:center; padding:1.5rem 0 1rem;">
            <div class="auth-badge">🎯 PATENT-ALIGNED PROTOTYPE</div>
            <h1 style="font-size:2.2rem;font-weight:800;margin:.4rem 0;">
                AI Personalized Career & Skill Gap Advisor
            </h1>
            <p style="color:#94A3B8;line-height:1.6;">
                Unified student profile • multi-source evidence • career matching •
                skill-gap prioritization • adaptive roadmap • reassessment
            </p>
        </div>
        """, unsafe_allow_html=True)
        with st.container(border=True):
            tab1, tab2 = st.tabs(["🔑 Sign In", "✨ Create Account"])
            with tab1:
                with st.form("login_form"):
                    username = st.text_input("Username", placeholder="demo")
                    password = st.text_input("Password", type="password", placeholder="demo123")
                    submit = st.form_submit_button("🚀 Sign In", type="primary", use_container_width=True)
                    if submit:
                        user = authenticate_user(username, password)
                        if user:
                            st.session_state.authenticated = True
                            st.session_state.user = user
                            st.rerun()
                        else:
                            st.error("Invalid username or password.")
                if st.button("⚡ Demo Login (demo / demo123)", use_container_width=True):
                    st.session_state.authenticated = True
                    st.session_state.user = authenticate_user("demo", "demo123")
                    st.rerun()
            with tab2:
                with st.form("signup_form"):
                    name = st.text_input("Full Name")
                    username = st.text_input("Choose Username")
                    email = st.text_input("Email")
                    password = st.text_input("Create Password", type="password")
                    confirm = st.text_input("Confirm Password", type="password")
                    submit = st.form_submit_button("✨ Register", type="primary", use_container_width=True)
                    if submit:
                        if not name.strip() or not username.strip() or not password.strip():
                            st.error("Full Name, Username and Password are required.")
                        elif len(password) < 4:
                            st.error("Password must be at least 4 characters.")
                        elif password != confirm:
                            st.error("Passwords do not match.")
                        else:
                            ok, msg = register_user(username, name, email, password)
                            if ok:
                                st.success(msg)
                                st.session_state.authenticated = True
                                st.session_state.user = authenticate_user(username, password)
                                st.rerun()
                            else:
                                st.error(msg)

if not st.session_state.authenticated:
    render_auth_page()
    st.stop()

# =========================================================
# HERO
# =========================================================
st.markdown("""
<div class="hero-banner">
    <div class="hero-title">🎯 AI-Based Personalized Career Recommendation & Dynamic Skill Gap Analysis</div>
    <div class="hero-subtitle">
        A unified workflow that combines academic information, technical skills,
        projects, certifications, interests, career goals and assessment evidence
        to generate career-specific skill gaps, prioritized learning steps and
        an updateable roadmap.
    </div>
    <div class="hero-tags">
        <span class="hero-tag">👤 Unified Student Profile</span>
        <span class="hero-tag">🧾 Multi-Source Evidence</span>
        <span class="hero-tag">🧠 Career Requirement Mapping</span>
        <span class="hero-tag">📊 Skill-Gap Prioritization</span>
        <span class="hero-tag">🗺️ Adaptive Roadmap</span>
        <span class="hero-tag">🔄 Closed-Loop Reassessment</span>
    </div>
</div>
""", unsafe_allow_html=True)

careers = load_careers()
categories = sorted(set(c["category"] for c in careers))

# =========================================================
# SIDEBAR: CAREER REQUIREMENT / FILTER CONTROLS
# =========================================================
with st.sidebar:
    user = st.session_state.user or {"full_name": "Student", "username": "student"}
    st.markdown(
        f"<div style='background:rgba(99,102,241,.12);border:1px solid rgba(129,140,248,.3);"
        f"border-radius:12px;padding:.9rem 1rem;margin-bottom:1rem;'>"
        f"<div style='font-size:.72rem;color:#94A3B8;font-weight:700;'>CURRENT USER</div>"
        f"<div style='font-size:1.05rem;color:#EEF2FF;font-weight:700;'>👤 {user.get('full_name','Student')}</div>"
        f"<div style='font-size:.8rem;color:#A5B4FC;'>@{user.get('username','student')}</div></div>",
        unsafe_allow_html=True
    )

    if st.button("🚪 Sign Out", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.analysis_done = False
        st.rerun()

    st.markdown("---")
    st.markdown("### 🎯 Career Requirement Mapping")
    target_career = st.selectbox(
        "Target / Selected Career",
        ["Auto-match from profile"] + [c["career"] for c in careers],
        help="A selected career becomes the target requirement profile for detailed gap analysis."
    )
    selected_category = st.selectbox("Domain / Track", ["All Domains"] + categories)
    min_match = st.slider("Minimum Match %", 0, 90, 0, 5)

    st.markdown("---")
    st.markdown("### ⚡ Profile Presets")
    presets = {
        "💻 Full Stack": "HTML, CSS, JavaScript, React, Node.js, SQL, Git, REST API",
        "🤖 AI / LLM": "Python, Machine Learning, Deep Learning, PyTorch, LLM, LangChain, RAG",
        "☁️ Cloud / DevOps": "Linux, Git, Docker, Kubernetes, AWS, CI/CD, Terraform",
        "🛡️ Cybersecurity": "Linux, Networking, Python, Wireshark, Cybersecurity, OWASP",
        "📊 Data Science": "Python, SQL, Statistics, Pandas, NumPy, Machine Learning",
    }
    cols = st.columns(2)
    for i, (name, skills) in enumerate(presets.items()):
        if cols[i % 2].button(name, use_container_width=True):
            st.session_state.skill_input_text = skills
            st.session_state.analysis_done = False
            st.rerun()

    st.markdown("---")
    st.caption(
        f"Career database: {len(careers)} careers • {len(categories)} domains. "
        "If careers.csv is present, its career requirements are used."
    )

# =========================================================
# 1. COMPREHENSIVE STUDENT PROFILE MODULE
# =========================================================
st.markdown("### 1. 👤 Comprehensive Student Profile")
st.caption(
    "Patent-aligned inputs: CGPA/academic information, skills, programming languages, "
    "projects, certifications, interests and career goal."
)

p1, p2, p3 = st.columns(3)
with p1:
    degree = st.text_input("Degree / Program", value="B.Tech CSE")
    institute = st.text_input("Institute / University", value="")
    cgpa = st.number_input("CGPA", min_value=0.0, max_value=10.0, value=6.71, step=0.01)
with p2:
    semester = st.number_input("Current Semester", min_value=1, max_value=12, value=4, step=1)
    interests_text = st.text_input("Interests", value="Technology, AI, Cloud")
    career_goal = st.text_input("Career Goal", value="")
with p3:
    programming_text = st.text_input("Programming Languages", value="Python, C++, JavaScript")
    project_count = st.number_input("Completed Projects", min_value=0, max_value=100, value=0, step=1)
    certification_count = st.number_input("Certifications", min_value=0, max_value=100, value=0, step=1)

# =========================================================
# 2. MULTI-SOURCE SKILL EVIDENCE
# =========================================================
st.markdown("### 2. 🧾 Multi-Source Skill Evidence")
st.caption(
    "Same skill can be supported by self-declaration, project work, certification and assessment. "
    "The engine combines these evidence sources into a structured skill profile."
)

e1, e2 = st.columns(2)
with e1:
    st.markdown("**Self-declared technical skills**")
    skill_text = st.text_area(
        "Skills",
        value=st.session_state.skill_input_text,
        height=85,
        label_visibility="collapsed",
        placeholder="Python, SQL, Git, DSA..."
    )
    st.session_state.skill_input_text = skill_text

    st.markdown("**Project-demonstrated skills / technologies**")
    project_skills_text = st.text_area(
        "Project skills",
        value=st.session_state.project_skills_text,
        height=80,
        label_visibility="collapsed",
        placeholder="React, Node.js, SQL, APIs..."
    )
    st.session_state.project_skills_text = project_skills_text

with e2:
    st.markdown("**Certification-supported skills / technologies**")
    certification_skills_text = st.text_area(
        "Certification skills",
        value=st.session_state.certification_skills_text,
        height=80,
        label_visibility="collapsed",
        placeholder="AWS, Linux, Python..."
    )
    st.session_state.certification_skills_text = certification_skills_text

    st.markdown("**Assessment-demonstrated skills**")
    assessment_skills_text = st.text_area(
        "Assessment skills",
        value=st.session_state.assessment_skills_text,
        height=80,
        label_visibility="collapsed",
        placeholder="DSA, SQL, Python..."
    )
    st.session_state.assessment_skills_text = assessment_skills_text

# =========================================================
# 3. ASSESSMENT MODULE
# =========================================================
st.markdown("### 3. 📝 Assessment Module")
st.caption("Technical, communication and grammar/English assessment results are incorporated into the profile.")

a1, a2, a3 = st.columns(3)
with a1:
    technical_assessment = st.slider("Technical Assessment Score", 0, 100, 60)
with a2:
    communication_score = st.slider("Communication Assessment", 0, 100, 60)
with a3:
    grammar_score = st.slider("Grammar / English Assessment", 0, 100, 60)

assessment_note = st.text_input(
    "Assessment / evidence note (optional)",
    placeholder="e.g. coding test, aptitude test, communication round, English test"
)

# =========================================================
# BUILD PROFILE + ANALYZE
# =========================================================
profile = {
    "degree": degree.strip(),
    "institute": institute.strip(),
    "cgpa": cgpa,
    "semester": semester,
    "interests": parse_skill_text(interests_text),
    "career_goal": career_goal.strip(),
    "programming_languages": parse_skill_text(programming_text),
    "project_count": project_count,
    "certification_count": certification_count,
    "skills": parse_skill_text(skill_text),
    "project_skills": parse_skill_text(project_skills_text),
    "certification_skills": parse_skill_text(certification_skills_text),
    "assessment_skills": parse_skill_text(assessment_skills_text),
    "technical_assessment": technical_assessment,
    "communication_score": communication_score,
    "grammar_score": grammar_score,
    "assessment_note": assessment_note.strip(),
}

# Technical assessment result itself is part of the evidence model.
# When an assessment skill is explicitly named, its confidence is reinforced.
if technical_assessment >= 70:
    profile["assessment_evidence_level"] = "strong"
elif technical_assessment >= 45:
    profile["assessment_evidence_level"] = "partial"
else:
    profile["assessment_evidence_level"] = "limited"

b1, b2, b3 = st.columns([3, 1, 1])
with b1:
    analyze_button = st.button(
        "🚀 Build Structured Profile & Analyze Careers",
        type="primary",
        use_container_width=True
    )
with b2:
    if st.button("🗑️ Clear Skill Evidence", use_container_width=True):
        st.session_state.skill_input_text = ""
        st.session_state.project_skills_text = ""
        st.session_state.certification_skills_text = ""
        st.session_state.assessment_skills_text = ""
        st.session_state.analysis_done = False
        st.rerun()
with b3:
    if st.button("🔄 Reassess Profile", use_container_width=True):
        st.session_state.analysis_done = True
        st.session_state.student_profile = profile
        st.session_state.reassessment_history.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "technical": technical_assessment,
            "communication": communication_score,
            "grammar": grammar_score,
        })
        st.rerun()

if analyze_button:
    if not profile["skills"] and not profile["project_skills"] and not profile["certification_skills"] and not profile["assessment_skills"]:
        st.warning("Please provide at least one skill/evidence source.")
        st.stop()

    filtered = careers
    if selected_category != "All Domains":
        filtered = [c for c in filtered if c["category"] == selected_category]

    results = [analyze_career(c, profile) for c in filtered]
    results.sort(key=lambda x: x["percentage"], reverse=True)

    # Selected target career is moved to the front for focused requirement mapping.
    if target_career != "Auto-match from profile":
        exact = [r for r in results if r["career"] == target_career]
        if exact:
            target_result = exact[0]
            results = [target_result] + [r for r in results if r is not target_result]

    # A declared career goal is also used as a target when it exactly matches
    # a known career and no explicit sidebar target was selected.
    elif career_goal.strip():
        goal = career_goal.strip().lower()
        exact = [r for r in results if r["career"].lower() == goal]
        if exact:
            target_result = exact[0]
            results = [target_result] + [r for r in results if r is not target_result]

    st.session_state.student_profile = profile
    st.session_state.student_skills = profile["skills"]
    st.session_state.results = results
    st.session_state.analysis_done = True

# =========================================================
# RESULTS
# =========================================================
if st.session_state.analysis_done and st.session_state.results:
    results = st.session_state.results
    profile = st.session_state.student_profile

    if selected_category != "All Domains":
        active_results = [r for r in results if r["category"] == selected_category]
    else:
        active_results = results
    active_results = [r for r in active_results if r["percentage"] >= min_match]

    if not active_results:
        st.info("No careers meet the current filter. Lower Minimum Match % in the sidebar.")
        st.stop()

    top = active_results[0]
    evidence_map, raw_evidence = build_evidence_map(profile)

    st.markdown("---")
    st.markdown("### 4. 🧠 Structured Student Skill Profile")

    sp1, sp2, sp3, sp4 = st.columns(4)
    sp1.metric("Academic Readiness", f"{academic_readiness(profile['cgpa']):.0f}%")
    sp2.metric("Technical Assessment", f"{profile['technical_assessment']}%")
    sp3.metric("Communication", f"{profile['communication_score']}%")
    sp4.metric("Grammar / English", f"{profile['grammar_score']}%")

    st.markdown("**Evidence-backed skills detected:**")
    if evidence_map:
        evidence_rows = []
        for skill, conf in sorted(evidence_map.items(), key=lambda x: -x[1]):
            evidence_rows.append({
                "Skill": skill.title(),
                "Evidence Strength": f"{conf*100:.0f}%",
                "Status": "Strong" if conf >= .75 else "Partial" if conf >= .45 else "Limited",
                "Sources": ", ".join(raw_evidence.get(skill, [])) if raw_evidence.get(skill) else "—",
            })
        st.dataframe(pd.DataFrame(evidence_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No structured evidence available yet.")

    st.markdown("### 5. 🎯 Career Matching & Requirement Mapping")
    st.caption(
        "Each career is represented as a requirement profile. Matching combines technical "
        "competencies with practical/project evidence, communication and academic information."
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Top Career Match", top["career"])
    k2.metric("Overall Alignment", f"{top['percentage']:.0f}%")
    k3.metric("Technical Alignment", f"{top['technical_pct']:.0f}%")
    k4.metric("Practical Evidence", f"{top['practical_pct']:.0f}%")

    tabs = st.tabs([
        "📊 Career Matching",
        "🔎 Skill-Gap Analysis",
        "📌 Gap Prioritization",
        "🗺️ Personalized Roadmap",
        "🔄 Reassessment"
    ])

    # -----------------------------------------------------
    # TAB 1: CAREER MATCHING
    # -----------------------------------------------------
    with tabs[0]:
        top_8 = active_results[:8]
        chart_df = pd.DataFrame({
            "Career": [r["career"] for r in top_8],
            "Overall Alignment": [round(r["percentage"]) for r in top_8],
            "Technical": [round(r["technical_pct"]) for r in top_8],
            "Practical": [round(r["practical_pct"]) for r in top_8],
        })
        chart = alt.Chart(chart_df).mark_bar(cornerRadiusTopRight=6, cornerRadiusBottomRight=6).encode(
            x=alt.X("Overall Alignment:Q", scale=alt.Scale(domain=[0, 100]), title="Alignment (%)"),
            y=alt.Y("Career:N", sort="-x", title=""),
            color=alt.Color("Overall Alignment:Q", scale=alt.Scale(scheme="viridis"), legend=None),
            tooltip=["Career", "Overall Alignment", "Technical", "Practical"],
        ).properties(height=320)
        st.altair_chart(chart, use_container_width=True)

        if profile.get("career_goal"):
            st.info(f"🎯 Declared career goal: **{profile['career_goal']}**")
        if target_career != "Auto-match from profile":
            st.info(f"🎯 Selected target career requirement profile: **{target_career}**")

        st.markdown("#### Requirement dimensions for the selected/top career")
        dim_df = pd.DataFrame({
            "Dimension": ["Technical", "Practical / Project Evidence", "Communication", "Academic"],
            "Current Evidence": [
                top["technical_pct"], top["practical_pct"],
                top["communication_pct"], top["academic_pct"]
            ]
        })
        st.bar_chart(dim_df.set_index("Dimension"))

    # -----------------------------------------------------
    # TAB 2: SKILL GAP ANALYSIS
    # -----------------------------------------------------
    with tabs[1]:
        search = st.text_input("🔍 Search career or skill", key="gap_search")
        view = active_results
        if search.strip():
            q = search.lower().strip()
            view = [
                r for r in active_results
                if q in r["career"].lower()
                or q in r["category"].lower()
                or any(q in s["skill"].lower() for s in r["strong"] + r["partial"] + r["missing"])
            ]

        for res in view:
            with st.expander(f"{res['career']} — {res['percentage']:.0f}%"):
                st.progress(min(res["percentage"] / 100.0, 1.0))
                d1, d2, d3 = st.columns(3)
                with d1:
                    st.markdown("**🟢 Strong / evidence-supported**")
                    if res["strong"]:
                        for s in res["strong"]:
                            st.markdown(
                                f"<span class='skill-badge badge-strong'>✔ {s['skill']} "
                                f"({s['confidence']*100:.0f}% evidence)</span>",
                                unsafe_allow_html=True
                            )
                    else:
                        st.caption("None")
                with d2:
                    st.markdown("**🟡 Partial**")
                    if res["partial"]:
                        for s in res["partial"]:
                            st.markdown(
                                f"<span class='skill-badge badge-partial'>~ {s['skill']} "
                                f"({s['confidence']*100:.0f}%)</span>",
                                unsafe_allow_html=True
                            )
                    else:
                        st.caption("None")
                with d3:
                    st.markdown("**🔴 Missing / insufficient**")
                    if res["missing"]:
                        for s in res["missing"]:
                            label = "HIGH" if s["weight"] >= 3 else "MED" if s["weight"] == 2 else "LOW"
                            cls = "pri-high" if s["weight"] >= 3 else "pri-med" if s["weight"] == 2 else "pri-low"
                            st.markdown(
                                f"<span class='skill-badge badge-missing'>{s['skill']} "
                                f"<span class='badge-priority {cls}'>{label}</span></span>",
                                unsafe_allow_html=True
                            )
                    else:
                        st.success("All mapped technical skills have evidence.")

    # -----------------------------------------------------
    # TAB 3: PRIORITIZATION
    # -----------------------------------------------------
    with tabs[2]:
        st.markdown("#### 📌 Career-Specific Skill-Gap Prioritization")
        st.caption(
            "Priority is based on career requirement weight plus prerequisite/dependency structure. "
            "This turns a list of gaps into an ordered development queue."
        )

        priority_career_name = st.selectbox(
            "Career to prioritize",
            [r["career"] for r in active_results],
            key="priority_career"
        )
        priority_res = next(r for r in active_results if r["career"] == priority_career_name)
        roadmap_items = generate_roadmap(priority_res, profile)

        priority_rows = []
        for idx, item in enumerate(roadmap_items, 1):
            dep_score, prereqs = dependency_score(item["skill"], profile["skills"])
            priority_value = item["weight"] * 10 + len(prereqs) * 5
            priority_rows.append({
                "Order": idx,
                "Skill Gap": item["skill"],
                "Career Weight": item["weight"],
                "Evidence": f"{item['confidence']*100:.0f}%",
                "Prerequisites Missing": ", ".join(x.title() for x in prereqs) if prereqs else "None",
                "Priority Value": priority_value,
            })
        if priority_rows:
            st.dataframe(pd.DataFrame(priority_rows), use_container_width=True, hide_index=True)
        else:
            st.success("No prioritized gaps for this career.")

        st.markdown("#### 🔮 What-If Skill Simulation")
        if priority_res["missing"]:
            sim_skill = st.selectbox(
                "If you learn this skill next...",
                [x["skill"] for x in priority_res["missing"]],
                key="what_if_skill"
            )
            career_obj = next(c for c in careers if c["career"] == priority_career_name)
            sim = what_if_analysis(career_obj, profile, sim_skill)
            q1, q2, q3 = st.columns(3)
            q1.metric("Current", f"{sim['before']:.0f}%")
            q2.metric("After simulated skill", f"{sim['after']:.0f}%", delta=f"{sim['improvement']:+.0f}%")
            q3.metric("Prerequisite Readiness", f"{sim['readiness']*100:.0f}%")
            if sim["missing_prereqs"]:
                st.warning("Prerequisites to address first: " + ", ".join(x.title() for x in sim["missing_prereqs"]))
            else:
                st.success("All mapped prerequisites are currently covered.")
        else:
            st.success("No missing skills to simulate for this career.")

    # -----------------------------------------------------
    # TAB 4: ADAPTIVE LEARNING ROADMAP
    # -----------------------------------------------------
    with tabs[3]:
        st.markdown("#### 🗺️ Personalized Learning Roadmap")
        roadmap_career_name = st.selectbox(
            "Choose target career",
            [r["career"] for r in active_results],
            key="roadmap_career"
        )
        roadmap_res = next(r for r in active_results if r["career"] == roadmap_career_name)
        items = generate_roadmap(roadmap_res, profile)

        if not items:
            st.success("🎉 No unresolved skill gaps detected for this career.")
        else:
            for step, item in enumerate(items, 1):
                priority = "HIGH" if item["weight"] >= 3 else "MEDIUM" if item["weight"] == 2 else "LOW"
                cls = "pri-high" if priority == "HIGH" else "pri-med" if priority == "MEDIUM" else "pri-low"
                st.markdown(
                    f"<div style='background:rgba(255,255,255,.04);border-left:4px solid #818CF8;"
                    f"border-radius:10px;padding:1rem 1.2rem;margin:.6rem 0;'>"
                    f"<div style='display:flex;justify-content:space-between;'>"
                    f"<b style='color:#FFFFFF;'>Step {step}: {item['skill'].title()}</b>"
                    f"<span class='badge-priority {cls}'>{priority}</span></div>"
                    f"<div style='color:#A5B4FC;margin-top:.35rem;'>"
                    f"Career relevance weight: {item['weight']} • Current evidence: {item['confidence']*100:.0f}%"
                    f"</div></div>",
                    unsafe_allow_html=True
                )
                if item["before"]:
                    st.warning("Foundation first: " + ", ".join(x.title() for x in item["before"]))
                else:
                    st.success("Ready to learn now — no unmet prerequisite in the dependency graph.")

            st.markdown("---")
            st.markdown("**Suggested learning resources (roadmap embodiment):**")
            st.write("Courses • Tutorials • Practice exercises • Projects • Certifications")

    # -----------------------------------------------------
    # TAB 5: CLOSED-LOOP REASSESSMENT
    # -----------------------------------------------------
    with tabs[4]:
        st.markdown("#### 🔄 Reassessment & Profile Update")
        st.caption(
            "After learning or another assessment, update the evidence above and use Reassess Profile. "
            "The career gaps and roadmap are recalculated from the new profile."
        )

        if st.session_state.reassessment_history:
            hist = pd.DataFrame(st.session_state.reassessment_history)
            st.dataframe(hist, use_container_width=True, hide_index=True)
        else:
            st.info("No reassessment event recorded yet.")

        r1, r2, r3 = st.columns(3)
        r1.metric("Current Technical Assessment", f"{profile['technical_assessment']}%")
        r2.metric("Current Communication", f"{profile['communication_score']}%")
        r3.metric("Current Grammar / English", f"{profile['grammar_score']}%")

        st.markdown("**Closed-loop flow:**")
        st.markdown(
            "Student Data → Assessment → Structured Skill Profile → Career Matching → "
            "Skill-Gap Analysis → Gap Prioritization → Learning Roadmap → Reassessment → Updated Profile & Roadmap"
        )

# =========================================================
# FOOTER
# =========================================================
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#94A3B8;font-size:.82rem;padding:1rem 0;'>"
    "AI-Based Personalized Career Recommendation and Dynamic Skill Gap Analysis System • "
    "Patent-aligned prototype • Streamlit"
    "</div>",
    unsafe_allow_html=True
)
