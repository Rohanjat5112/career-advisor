import streamlit as st
import pandas as pd
import altair as alt
import re
import sqlite3
import hashlib
from difflib import SequenceMatcher
from collections import Counter

# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Career & Skill Gap AI Advisor",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# DATABASE & AUTHENTICATION SETUP (SQLite)
# =========================================================

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
    # Check if default demo user exists
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
        "SELECT username, full_name, email FROM users WHERE LOWER(username) = LOWER(?) AND password_hash = ?",
        (username.strip(), pwd_hash)
    )
    user = c.fetchone()
    conn.close()
    if user:
        return {"username": user[0], "full_name": user[1], "email": user[2]}
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
        return True, "Account created successfully!"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "This username already exists. Please pick another one."
    except Exception as e:
        conn.close()
        return False, f"Error creating account: {str(e)}"

# =========================================================
# SESSION STATE INITIALIZATION
# =========================================================

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "user" not in st.session_state:
    st.session_state.user = None

if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False

if "student_skills" not in st.session_state:
    st.session_state.student_skills = []

if "results" not in st.session_state:
    st.session_state.results = []

if "skill_input_text" not in st.session_state:
    st.session_state.skill_input_text = "Python, SQL, Git, DSA, Machine Learning"

# =========================================================
# ADVANCED CUSTOM STYLING (Modern UI / Glassmorphism)
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

# =========================================================
# AUTHENTICATION SCREEN (LOGIN / SIGN UP)
# =========================================================

def render_auth_page():
    _, center_col, _ = st.columns([1, 2, 1])
    with center_col:
        st.markdown("""
        <div style="text-align: center; padding: 1.2rem 0 0.8rem 0;">
            <div class="auth-badge">🚀 NEXT-GEN AI CAREER PLATFORM</div>
            <h1 style="font-size: 2.3rem; font-weight: 800; margin-top: 0.3rem; margin-bottom: 0.4rem; background: linear-gradient(90deg, #FFFFFF 0%, #C7D2FE 50%, #818CF8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: -0.02em;">
                Career & Skill Gap AI Advisor
            </h1>
            <p style="color: #94A3B8; font-size: 0.98rem; max-width: 580px; margin: 0 auto 0.8rem auto; line-height: 1.5;">
                Sign in to analyze your skills across <b>64+ tech careers</b>, run What-If simulations, and unlock personalized roadmaps.
            </p>
            <div style="margin-bottom: 1.2rem;">
                <span class="auth-tag">🎯 64+ Tech Roles</span>
                <span class="auth-tag">🔮 What-If Simulator</span>
                <span class="auth-tag">🗺️ Smart Roadmap</span>
                <span class="auth-tag">🔒 SQLite Protected</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.container(border=True):
            auth_tab1, auth_tab2 = st.tabs(["🔑 Sign In", "✨ Create Account"])

            with auth_tab1:
                st.markdown("<br>", unsafe_allow_html=True)
                with st.form("login_form"):
                    username = st.text_input("Username", placeholder="e.g. rohan_jat or demo")
                    password = st.text_input("Password", type="password", placeholder="Enter your password")
                    submit_login = st.form_submit_button("🚀 Sign In to Dashboard", type="primary", use_container_width=True)

                    if submit_login:
                        if not username.strip() or not password.strip():
                            st.error("Please enter both username and password.")
                        else:
                            user = authenticate_user(username, password)
                            if user:
                                st.session_state.authenticated = True
                                st.session_state.user = user
                                st.success(f"Welcome back, {user['full_name']}! Redirecting to dashboard...")
                                st.rerun()
                            else:
                                st.error("❌ Invalid username or password. Please try again.")

                st.markdown("<div style='text-align:center; margin: 1.3rem 0 0.8rem 0; color: #64748B; font-size: 0.85rem; font-weight: 600;'>— OR QUICK 1-CLICK ACCESS —</div>", unsafe_allow_html=True)
                if st.button("⚡ Instant Demo Login (demo / demo123)", use_container_width=True):
                    user = authenticate_user("demo", "demo123")
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.rerun()
                st.caption("💡 Instant access without registration for quick testing and demonstration.")

            with auth_tab2:
                st.markdown("<br>", unsafe_allow_html=True)
                with st.form("signup_form"):
                    reg_name = st.text_input("Full Name", placeholder="e.g. Rohan Jat")
                    reg_username = st.text_input("Choose Username", placeholder="e.g. rohan_jat")
                    reg_email = st.text_input("Email Address", placeholder="e.g. rohanjat@example.com")
                    reg_password = st.text_input("Create Password", type="password", placeholder="At least 4 characters")
                    reg_confirm = st.text_input("Confirm Password", type="password", placeholder="Re-enter password to confirm")
                    submit_reg = st.form_submit_button("✨ Register & Enter Dashboard", type="primary", use_container_width=True)

                    if submit_reg:
                        if not reg_name.strip() or not reg_username.strip() or not reg_password.strip():
                            st.error("Please fill in all required fields (Full Name, Username, Password).")
                        elif len(reg_password) < 4:
                            st.error("Password must be at least 4 characters long.")
                        elif reg_password != reg_confirm:
                            st.error("Passwords do not match. Please verify.")
                        else:
                            success, msg = register_user(reg_username, reg_name, reg_email, reg_password)
                            if success:
                                st.success("🎉 Account created successfully! Logging you in...")
                                user = authenticate_user(reg_username, reg_password)
                                st.session_state.authenticated = True
                                st.session_state.user = user
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")

        st.markdown("""
        <div style="text-align:center; color:#64748B; font-size:0.82rem; margin-top:1.5rem;">
            🔒 Secure SQLite Database (users.db) • Passwords Encrypted with SHA-256
        </div>
        """, unsafe_allow_html=True)

# Check if authenticated
if not st.session_state.authenticated:
    render_auth_page()
    st.stop()

# =========================================================
# COMPREHENSIVE SKILL ALIASES & NORMALIZATION
# =========================================================

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
    skill = skill.lower().strip()
    skill = re.sub(r"\s+", " ", skill)
    if skill in ALIASES:
        return ALIASES[skill]
    compact = skill.replace(" ", "").replace("-", "").replace(".", "")
    if compact in ALIASES:
        return ALIASES[compact]
    return skill

# =========================================================
# SIMILARITY & COVERAGE ALGORITHM
# =========================================================

def similarity(a, b):
    a = normalize_skill(a)
    b = normalize_skill(b)
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.90
    return SequenceMatcher(None, a, b).ratio()

def is_skill_covered(required_skill, student_skills):
    best_score = 0.0
    for student_skill in student_skills:
        score = similarity(required_skill, student_skill)
        best_score = max(best_score, score)

    if best_score >= 0.80:
        return "strong", best_score
    if best_score >= 0.62:
        return "partial", best_score
    return "missing", best_score

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
    missing_prereqs = []
    covered = 0
    for p in prereqs:
        st_val, _ = is_skill_covered(p, student_skills)
        if st_val == "strong":
            covered += 1
        elif st_val == "partial":
            covered += 0.5
        else:
            missing_prereqs.append(p)
    return covered / len(prereqs), missing_prereqs

# =========================================================
# DATA LOADING & CACHING
# =========================================================

@st.cache_data
def load_careers():
    df = pd.read_csv("careers.csv")
    careers = []
    for _, row in df.iterrows():
        skill_parts = str(row["skills"]).split(";")
        skills = []
        for part in skill_parts:
            part = part.strip()
            if ":" not in part:
                continue
            skill, weight = part.rsplit(":", 1)
            skills.append({
                "name": normalize_skill(skill),
                "original_name": skill.strip(),
                "weight": int(weight)
            })
        careers.append({
            "career": row["career"],
            "category": row["category"],
            "skills": skills
        })
    return careers

# =========================================================
# CAREER ANALYSIS LOGIC
# =========================================================

def analyze_career(career, student_skills):
    total_weight = 0
    earned_weight = 0
    strong = []
    partial = []
    missing = []

    for item in career["skills"]:
        s_name = item["name"]
        orig_name = item["original_name"]
        w = item["weight"]
        total_weight += w

        status, score = is_skill_covered(s_name, student_skills)
        if status == "strong":
            earned_weight += w
            strong.append({"skill": orig_name, "weight": w})
        elif status == "partial":
            earned_weight += w * 0.5
            partial.append({"skill": orig_name, "weight": w})
        else:
            missing.append({"skill": orig_name, "weight": w})

    pct = 0 if total_weight == 0 else (earned_weight / total_weight) * 100
    missing.sort(key=lambda x: x["weight"], reverse=True)

    return {
        "career": career["career"],
        "category": career["category"],
        "percentage": pct,
        "strong": strong,
        "partial": partial,
        "missing": missing,
        "total_skills": len(career["skills"])
    }

def what_if_analysis(career, student_skills, new_skill):
    before = analyze_career(career, student_skills)
    simulated_skills = student_skills.copy()
    simulated_skills.append(new_skill)
    after = analyze_career(career, simulated_skills)
    improvement = after["percentage"] - before["percentage"]
    score, missing_prereqs = dependency_score(new_skill, student_skills)
    return {
        "before": before["percentage"],
        "after": after["percentage"],
        "improvement": improvement,
        "readiness": score,
        "missing_prereqs": missing_prereqs
    }

def generate_roadmap(career_result, student_skills):
    roadmap = []
    missing = career_result["missing"]
    for item in missing:
        skill = item["skill"]
        _, missing_prereqs = dependency_score(skill, student_skills)
        roadmap.append({
            "skill": skill,
            "weight": item["weight"],
            "before": missing_prereqs
        })
    roadmap.sort(key=lambda x: (len(x["before"]), -x["weight"]))
    return roadmap

# =========================================================
# HEADER & HERO BANNER
# =========================================================

st.markdown("""
<div class="hero-banner">
    <div class="hero-title">⚡ Tech Career & Skill Gap AI Advisor</div>
    <div class="hero-subtitle">
        Analyze your skill profile against <b>64+ industry technology careers</b>. Identify skill gaps, test career improvements with What-If simulations, and generate an actionable learning roadmap.
    </div>
    <div class="hero-tags">
        <span class="hero-tag">🎯 Smart Weighted Matching</span>
        <span class="hero-tag">📚 12 Tech Domains</span>
        <span class="hero-tag">🔮 What-If Simulator</span>
        <span class="hero-tag">🗺️ Dependency-Aware Roadmap</span>
        <span class="hero-tag">💡 High-ROI Skill Discovery</span>
    </div>
</div>
""", unsafe_allow_html=True)

# =========================================================
# SIDEBAR CONTROLS
# =========================================================

careers = load_careers()
all_categories = sorted(list(set(c["category"] for c in careers)))

with st.sidebar:
    # User Profile Header
    current_user = st.session_state.user or {"full_name": "Student", "username": "student"}
    st.markdown(f"""
    <div style="background: rgba(99, 102, 241, 0.12); border: 1px solid rgba(129, 140, 248, 0.3); border-radius: 12px; padding: 0.9rem 1.1rem; margin-bottom: 1rem;">
        <div style="font-size: 0.75rem; color: #94A3B8; text-transform: uppercase; font-weight: 700; letter-spacing: 0.05em;">Current User</div>
        <div style="font-size: 1.1rem; font-weight: 700; color: #EEF2FF; margin-top: 0.2rem;">👤 {current_user.get('full_name', 'Student')}</div>
        <div style="font-size: 0.85rem; color: #A5B4FC;">@{current_user.get('username', 'user')}</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🚪 Sign Out", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.analysis_done = False
        st.rerun()

    st.markdown("---")
    st.markdown("### 🛠️ Career Filters & Settings")
    
    selected_category = st.selectbox(
        "Domain / Track",
        ["All Domains"] + all_categories,
        help="Filter analysis by specific tech field"
    )
    
    min_match_filter = st.slider(
        "Filter by Minimum Match %",
        min_value=0,
        max_value=90,
        value=0,
        step=5,
        help="Only display careers that match at or above this percentage"
    )

    st.markdown("---")
    st.markdown("### 🎓 Quick Profile Presets")
    st.caption("Click any profile to instantly test realistic skillsets:")

    PRESETS = {
        "💻 Full Stack Web": "HTML, CSS, JavaScript, React, Node.js, Express, MongoDB, Git, REST API",
        "📊 Data Scientist": "Python, SQL, Statistics, Machine Learning, Pandas, Scikit-Learn, Data Visualization",
        "🤖 AI & LLM Engineer": "Python, Machine Learning, Deep Learning, PyTorch, LLM, LangChain, RAG",
        "☁️ DevOps & Cloud": "Linux, Git, Docker, Kubernetes, AWS, CI/CD, Terraform, Bash Scripting",
        "🛡️ Cybersecurity": "Linux, Networking, Python, Wireshark, Cybersecurity, Ethical Hacking, SIEM",
        "📱 Mobile App Dev": "Kotlin, Java, Android SDK, Jetpack Compose, Git, REST API",
        "🎨 UI/UX Designer": "Figma, UI Design, UX Design, Wireframing, Prototyping, Design Systems",
        "⚡ C++ / Core Systems": "C++, DSA, OOP, System Design, Multithreading, Linux, SQL"
    }

    preset_cols = st.columns(2)
    p_idx = 0
    for name, p_skills in PRESETS.items():
        col = preset_cols[p_idx % 2]
        if col.button(name, use_container_width=True):
            st.session_state.skill_input_text = p_skills
            st.session_state.analysis_done = False
            st.rerun()
        p_idx += 1

    st.markdown("---")
    st.markdown(f"**Database Info:** `{len(careers)}` Tech Careers loaded across `{len(all_categories)}` categories.")

# =========================================================
# SKILL INPUT SECTION
# =========================================================

st.markdown("### 1. ✍️ Enter Your Tech Skills")

# Quick skill chips
st.markdown("<small style='color:#94A3B8;'>Click to quickly append popular skills:</small>", unsafe_allow_html=True)
quick_skills_list = [
    "Python", "JavaScript", "SQL", "React", "Docker", "Git", 
    "AWS", "Linux", "Machine Learning", "DSA", "Node.js", 
    "Kubernetes", "Figma", "C++", "Java", "HTML/CSS"
]

quick_cols = st.columns(8)
for i, q_skill in enumerate(quick_skills_list):
    col = quick_cols[i % 8]
    if col.button(f"+{q_skill}", key=f"quick_{q_skill}", use_container_width=True):
        current = st.session_state.skill_input_text.strip()
        if current:
            st.session_state.skill_input_text = current + f", {q_skill}"
        else:
            st.session_state.skill_input_text = q_skill
        st.rerun()

skill_text = st.text_area(
    label="Skills (comma-separated):",
    value=st.session_state.skill_input_text,
    height=90,
    placeholder="e.g. Python, SQL, Git, React, Docker, Machine Learning, HTML, CSS..."
)
st.session_state.skill_input_text = skill_text

action_col1, action_col2, action_col3 = st.columns([3, 1, 2])
with action_col1:
    analyze_button = st.button("🚀 Analyze My Careers", type="primary", use_container_width=True)
with action_col2:
    if st.button("🗑️ Clear", use_container_width=True):
        st.session_state.skill_input_text = ""
        st.session_state.analysis_done = False
        st.rerun()

# =========================================================
# TRIGGER ANALYSIS
# =========================================================

if analyze_button:
    if not skill_text.strip():
        st.warning("⚠️ Please enter at least one skill or select a quick preset from the sidebar.")
        st.session_state.analysis_done = False
        st.stop()

    student_skills = []
    for s in skill_text.split(","):
        s_clean = s.strip()
        if s_clean:
            student_skills.append(normalize_skill(s_clean))

    filtered_careers = careers
    if selected_category != "All Domains":
        filtered_careers = [c for c in careers if c["category"] == selected_category]

    results = []
    for c in filtered_careers:
        res = analyze_career(c, student_skills)
        results.append(res)

    results.sort(key=lambda x: x["percentage"], reverse=True)

    st.session_state.student_skills = student_skills
    st.session_state.results = results
    st.session_state.analysis_done = True

# =========================================================
# RESULTS DISPLAY (TABS & MODERN DASHBOARD)
# =========================================================

if st.session_state.analysis_done and st.session_state.results:
    results = st.session_state.results
    student_skills = st.session_state.student_skills

    # Filter by user sidebar settings
    if selected_category != "All Domains":
        active_results = [r for r in results if r["category"] == selected_category]
    else:
        active_results = results

    active_results = [r for r in active_results if r["percentage"] >= min_match_filter]

    st.markdown("---")

    if not active_results:
        st.info(f"No careers match your current filter threshold (≥ {min_match_filter}%). Lower the slider in the sidebar to see all matches.")
        st.stop()

    top_result = active_results[0]
    strong_matches = sum(1 for r in active_results if r["percentage"] >= 75)
    moderate_matches = sum(1 for r in active_results if 50 <= r["percentage"] < 75)
    total_analyzed = len(active_results)

    # 4-Column KPI Metric Cards
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">🏆 Top Match Career</div>
            <div class="metric-value" style="font-size:1.35rem; color:#818CF8;">{top_result['career']}</div>
            <div class="metric-sub">{top_result['category']}</div>
        </div>
        """, unsafe_allow_html=True)
    with kpi2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">🎯 Highest Match Score</div>
            <div class="metric-value" style="color:#34D399;">{round(top_result['percentage'])}%</div>
            <div class="metric-sub">Best industry alignment</div>
        </div>
        """, unsafe_allow_html=True)
    with kpi3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">🟢 Strong Matches (≥75%)</div>
            <div class="metric-value" style="color:#10B981;">{strong_matches}</div>
            <div class="metric-sub">Careers you are ready for</div>
        </div>
        """, unsafe_allow_html=True)
    with kpi4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">🟡 Moderate Matches (50-74%)</div>
            <div class="metric-value" style="color:#FBBF24;">{moderate_matches}</div>
            <div class="metric-sub">Requires 1-2 key skills</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Tabs for modern navigation
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Top Matches & High-ROI Skills",
        "📋 All Careers Breakdown",
        "🔮 What-If Simulator",
        "🗺️ Personalized Learning Roadmap"
    ])

    # -----------------------------------------------------
    # TAB 1: EXECUTIVE SUMMARY & HIGH ROI SKILLS
    # -----------------------------------------------------
    with tab1:
        c_left, c_right = st.columns([3, 2])
        with c_left:
            st.markdown("#### 📈 Top 8 Career Fit Comparison")
            top_8 = active_results[:8]
            chart_df = pd.DataFrame({
                "Career": [r["career"] for r in top_8],
                "Match Percentage": [round(r["percentage"]) for r in top_8],
                "Category": [r["category"] for r in top_8]
            })

            chart = alt.Chart(chart_df).mark_bar(cornerRadiusTopRight=6, cornerRadiusBottomRight=6).encode(
                x=alt.X("Match Percentage:Q", scale=alt.Scale(domain=[0, 100]), title="Match (%)"),
                y=alt.Y("Career:N", sort="-x", title=""),
                color=alt.Color("Match Percentage:Q", scale=alt.Scale(scheme="viridis"), legend=None),
                tooltip=["Career", "Category", "Match Percentage"]
            ).properties(height=320)

            st.altair_chart(chart, use_container_width=True)

        with c_right:
            st.markdown("#### 💡 High-ROI Skills To Learn Next")
            st.caption("These missing skills appear most frequently across your top matching careers. Mastering them gives the highest career boost:")

            missing_pool = []
            for r in active_results[:10]:
                for m in r["missing"]:
                    missing_pool.append(m["skill"])

            top_missing = Counter(missing_pool).most_common(5)
            if top_missing:
                for skill_name, freq in top_missing:
                    st.markdown(f"""
                    <div style="background:rgba(255,255,255,0.05); border-left:4px solid #6366F1; padding:0.6rem 0.9rem; border-radius:6px; margin-bottom:0.45rem;">
                        <strong style="color:#EEF2FF; font-size:0.95rem;">{skill_name}</strong>
                        <span style="float:right; font-size:0.82rem; color:#A5B4FC; font-weight:600;">Unlocks {freq} top careers</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("🎉 Amazing! You have zero missing skills across your top careers!")

        st.markdown("---")
        st.markdown("#### 🌟 Top 3 Career Spotlight")
        spot_cols = st.columns(3)
        for idx, res in enumerate(active_results[:3]):
            with spot_cols[idx]:
                score = round(res["percentage"])
                color_class = "match-green" if score >= 75 else ("match-amber" if score >= 50 else "match-red")
                st.markdown(f"""
                <div class="spotlight-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                        <span style="font-size:0.8rem; color:#C7D2FE; font-weight:700;">{res['category'].upper()}</span>
                        <span class="match-pill {color_class}">{score}% Match</span>
                    </div>
                    <h3 style="margin-top:0.2rem; margin-bottom:0.6rem; color:#FFFFFF;">{res['career']}</h3>
                    <div style="margin-bottom:0.5rem;">
                        <small style="color:#94A3B8;">✅ Covered: </small>
                        <b style="color:#34D399;">{len(res['strong'])} skills</b> | 
                        <small style="color:#94A3B8;">❌ Missing: </small>
                        <b style="color:#F87171;">{len(res['missing'])} skills</b>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if res["missing"]:
                    st.markdown("**Key skills to unlock 100%:**")
                    for m in res["missing"][:2]:
                        st.markdown(f"• `{m['skill']}` (Priority: {['LOW','MEDIUM','HIGH'][m['weight']-1]})")

    # -----------------------------------------------------
    # TAB 2: EXPLORE ALL CAREERS
    # -----------------------------------------------------
    with tab2:
        search_query = st.text_input("🔍 Search career or skill within results:", "")

        filtered_view = active_results
        if search_query.strip():
            sq = search_query.lower().strip()
            filtered_view = [
                r for r in active_results
                if sq in r["career"].lower() or sq in r["category"].lower() or any(sq in s["skill"].lower() for s in r["strong"] + r["missing"])
            ]

        st.caption(f"Showing {len(filtered_view)} careers (sorted by highest match):")

        for res in filtered_view:
            pct = round(res["percentage"])
            if pct >= 75:
                tag_label = "🟢 Strong Match"
                bar_color = "#10B981"
            elif pct >= 50:
                tag_label = "🟡 Moderate Match"
                bar_color = "#F59E0B"
            else:
                tag_label = "🔴 Skill Gap"
                bar_color = "#EF4444"

            title_text = f"{res['career']} — {pct}% | {res['category']} ({tag_label})"
            with st.expander(title_text):
                st.progress(min(pct / 100, 1.0))

                s_col1, s_col2, s_col3 = st.columns([1, 1, 1.2])
                with s_col1:
                    st.markdown("**✅ Strong Skills:**")
                    if res["strong"]:
                        for s in res["strong"]:
                            st.markdown(f"<span class='skill-badge badge-strong'>✔ {s['skill']}</span>", unsafe_allow_html=True)
                    else:
                        st.caption("None yet")

                with s_col2:
                    st.markdown("**🟡 Partial Skills:**")
                    if res["partial"]:
                        for s in res["partial"]:
                            st.markdown(f"<span class='skill-badge badge-partial'>~ {s['skill']}</span>", unsafe_allow_html=True)
                    else:
                        st.caption("None")

                with s_col3:
                    st.markdown("**❌ Missing Skills to Learn:**")
                    if res["missing"]:
                        for s in res["missing"]:
                            pri_class = "pri-high" if s["weight"] == 3 else ("pri-med" if s["weight"] == 2 else "pri-low")
                            pri_label = "HIGH" if s["weight"] == 3 else ("MED" if s["weight"] == 2 else "LOW")
                            st.markdown(f"<span class='skill-badge badge-missing'>{s['skill']} <span class='badge-priority {pri_class}'>{pri_label}</span></span>", unsafe_allow_html=True)
                    else:
                        st.success("🎉 100% Complete! All required skills covered.")

    # -----------------------------------------------------
    # TAB 3: WHAT-IF SIMULATOR
    # -----------------------------------------------------
    with tab3:
        st.markdown("#### 🔮 What-If Career Simulation Engine")
        st.write("Select any target career and choose a skill you're considering learning. See exactly how much your match score will improve and verify prerequisite readiness.")

        sim_career_names = [r["career"] for r in active_results]
        if sim_career_names:
            sim_col1, sim_col2 = st.columns(2)
            with sim_col1:
                selected_career_name = st.selectbox(
                    "Select Target Career:",
                    sim_career_names,
                    key="sim_career_select"
                )
            selected_res = next(r for r in active_results if r["career"] == selected_career_name)
            missing_for_sim = [m["skill"] for m in selected_res["missing"]]

            with sim_col2:
                if missing_for_sim:
                    selected_skill_sim = st.selectbox(
                        "Select Skill to Learn:",
                        missing_for_sim,
                        key=f"sim_skill_{selected_career_name}"
                    )
                else:
                    selected_skill_sim = None
                    st.info("No missing skills for this career! You are already at 100% match.")

            if selected_skill_sim:
                career_obj = next(c for c in careers if c["career"] == selected_career_name)
                sim_res = what_if_analysis(career_obj, student_skills, selected_skill_sim)

                st.markdown("<br>", unsafe_allow_html=True)
                sc1, sc2, sc3 = st.columns(3)
                sc1.metric("Current Match", f"{round(sim_res['before'])}%")
                sc2.metric("After Learning", f"{round(sim_res['after'])}%", delta=f"+{round(sim_res['improvement'])}%")
                sc3.metric("Match Score Boost", f"+{round(sim_res['improvement'])}%")

                st.markdown("<br>", unsafe_allow_html=True)
                if sim_res["missing_prereqs"]:
                    st.warning(f"⚠️ **Prerequisite Advisory for {selected_skill_sim}:** Before learning this skill, it is strongly recommended to learn: **{', '.join([p.title() for p in sim_res['missing_prereqs']])}**.")
                else:
                    st.success(f"✅ **Ready to Learn:** You have all foundational prerequisites to master **{selected_skill_sim}** immediately!")

    # -----------------------------------------------------
    # TAB 4: PERSONALIZED ROADMAP
    # -----------------------------------------------------
    with tab4:
        st.markdown("#### 🗺️ Personalized Learning Roadmap")
        st.write("Generate a structured, dependency-aware step-by-step learning path for your desired tech career.")

        roadmap_career_name = st.selectbox(
            "Choose Career for Learning Roadmap:",
            [r["career"] for r in active_results],
            key="roadmap_career_select"
        )

        roadmap_res = next(r for r in active_results if r["career"] == roadmap_career_name)
        roadmap_items = generate_roadmap(roadmap_res, student_skills)

        if not roadmap_items:
            st.success(f"🎉 Congratulations! You have fully satisfied all skill requirements for **{roadmap_career_name}**!")
        else:
            for step_num, item in enumerate(roadmap_items, start=1):
                pri_label = "HIGH Priority" if item["weight"] == 3 else ("MEDIUM Priority" if item["weight"] == 2 else "LOW Priority")
                pri_badge = "pri-high" if item["weight"] == 3 else ("pri-med" if item["weight"] == 2 else "pri-low")

                with st.container():
                    st.markdown(f"""
                    <div style="background:rgba(255,255,255,0.04); border-left:4px solid #818CF8; border-radius:10px; padding:1rem 1.25rem; margin-bottom:0.8rem;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <h4 style="margin:0; color:#FFFFFF;">Step {step_num}: Learn {item['skill'].title()}</h4>
                            <span class="badge-priority {pri_badge}">{pri_label}</span>
                        </div>
                    """, unsafe_allow_html=True)

                    if item["before"]:
                        st.markdown(f"<p style='color:#FBBF24; margin:0.4rem 0 0 0; font-size:0.88rem;'>⚠️ <b>Foundations needed first:</b> {', '.join([b.title() for b in item['before']])}</p></div>", unsafe_allow_html=True)
                    else:
                        st.markdown("<p style='color:#34D399; margin:0.4rem 0 0 0; font-size:0.88rem;'>✅ <b>Ready to learn now:</b> No unmet prerequisites.</p></div>", unsafe_allow_html=True)

# =========================================================
# FOOTER
# =========================================================

st.markdown("---")
st.markdown("""
<div style="text-align:center; color:#94A3B8; font-size:0.85rem; padding:1rem 0;">
    Career & Skill Gap AI Advisor • Built with Streamlit • 64+ Tech Careers • Comprehensive Industry Benchmark
</div>
""", unsafe_allow_html=True)
