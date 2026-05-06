import streamlit as st
import sqlite3
import hashlib
import os
import re
from datetime import datetime, date, timezone, timedelta

# ─────────────────────────────────────────────
#  قاعدة البيانات
# ─────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "farm.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS workers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL, phone TEXT NOT NULL,
        experience_years INTEGER NOT NULL, skills TEXT NOT NULL,
        password TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
        applied_at TEXT NOT NULL, notes TEXT DEFAULT '')""")
    c.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL, description TEXT NOT NULL,
        time_slot TEXT NOT NULL, assigned_to TEXT NOT NULL DEFAULT 'all',
        task_date TEXT NOT NULL, created_at TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS task_completions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL, worker_id INTEGER NOT NULL,
        completed_at TEXT NOT NULL, UNIQUE(task_id, worker_id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, value TEXT NOT NULL)""")
    c.execute("SELECT value FROM settings WHERE key='admin_username'")
    if not c.fetchone():
        c.execute("INSERT INTO settings VALUES ('admin_username','admin')")
        c.execute("INSERT INTO settings VALUES ('admin_password',?)",
                  (hash_password("farm123"),))
    try:
        c.execute("ALTER TABLE workers ADD COLUMN medals TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def get_admin_credentials():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT key,value FROM settings WHERE key IN ('admin_username','admin_password')")
    rows = {r["key"]: r["value"] for r in c.fetchall()}
    conn.close()
    return rows.get("admin_username","admin"), rows.get("admin_password","")

def verify_admin_password(password: str) -> bool:
    _, stored = get_admin_credentials()
    return hash_password(password) == stored

def update_admin_credentials(new_username: str, new_password: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE settings SET value=? WHERE key='admin_username'", (new_username,))
    c.execute("UPDATE settings SET value=? WHERE key='admin_password'", (hash_password(new_password),))
    conn.commit(); conn.close()

def register_worker(name, phone, experience_years, skills, password):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO workers (name,phone,experience_years,skills,password,status,applied_at) VALUES (?,?,?,?,?,?,?)",
                  (name, phone, experience_years, skills, hash_password(password), "pending",
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True, "تم تسجيل طلبك بنجاح!"
    except sqlite3.IntegrityError:
        return False, "يوجد عامل مسجّل بهذا الاسم. يرجى استخدام اسم مختلف."
    finally:
        conn.close()

def login_worker(name, password):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM workers WHERE name=? AND password=?", (name, hash_password(password)))
    row = c.fetchone(); conn.close()
    return dict(row) if row else None

def get_all_workers():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM workers ORDER BY applied_at DESC")
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def update_worker_status(worker_id, status, notes=""):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE workers SET status=?,notes=? WHERE id=?", (status, notes, worker_id))
    conn.commit(); conn.close()

def update_worker_medals(worker_id: int, medals: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE workers SET medals=? WHERE id=?", (medals, worker_id))
    conn.commit(); conn.close()

def get_worker_by_id(worker_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM workers WHERE id=?", (worker_id,))
    row = c.fetchone(); conn.close()
    return dict(row) if row else None

def get_tasks(worker_id=None):
    conn = get_connection()
    c = conn.cursor()
    if worker_id:
        c.execute("SELECT * FROM tasks WHERE assigned_to='all' OR assigned_to=? ORDER BY time_slot",
                  (str(worker_id),))
    else:
        c.execute("SELECT * FROM tasks ORDER BY time_slot")
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def add_task(title, description, time_slot, assigned_to, task_date):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO tasks (title,description,time_slot,assigned_to,task_date,created_at) VALUES (?,?,?,?,?,?)",
              (title, description, time_slot, assigned_to, task_date,
               datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit(); conn.close()

def delete_task(task_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    c.execute("DELETE FROM task_completions WHERE task_id=?", (task_id,))
    conn.commit(); conn.close()

def mark_task_done(task_id, worker_id):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO task_completions (task_id,worker_id,completed_at) VALUES (?,?,?)",
                  (task_id, worker_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit(); return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def unmark_task_done(task_id, worker_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM task_completions WHERE task_id=? AND worker_id=?", (task_id, worker_id))
    conn.commit(); conn.close()

def is_task_done_by_worker(task_id, worker_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT 1 FROM task_completions WHERE task_id=? AND worker_id=?", (task_id, worker_id))
    result = c.fetchone() is not None; conn.close(); return result

def get_completions_for_task(task_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""SELECT tc.worker_id, tc.completed_at, w.name
                 FROM task_completions tc JOIN workers w ON w.id=tc.worker_id
                 WHERE tc.task_id=? ORDER BY tc.completed_at""", (task_id,))
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

def get_all_completions():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""SELECT tc.task_id, tc.worker_id, tc.completed_at,
                        w.name as worker_name, t.title as task_title
                 FROM task_completions tc
                 JOIN workers w ON w.id=tc.worker_id
                 JOIN tasks t ON t.id=tc.task_id
                 ORDER BY tc.completed_at DESC""")
    rows = [dict(r) for r in c.fetchall()]; conn.close(); return rows

# ─────────────────────────────────────────────
#  إعداد التطبيق
# ─────────────────────────────────────────────
init_db()

st.set_page_config(
    page_title="مزرعة الشاوية",
    page_icon=":material/agriculture:",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS مشترك لجميع الصفحات
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800;900&display=swap');
html, body, [class*="css"] { font-family: 'Tajawal', sans-serif !important; direction: rtl; text-align: right; }
[data-testid="stAppViewContainer"] { background: linear-gradient(160deg, #0a1a10 0%, #0d2b1e 50%, #0a1a10 100%); min-height: 100vh; }
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stSidebar"] { display: none !important; }
[data-testid="InputInstructions"] { display: none !important; }
footer { display: none; }
p, li, span { color: rgba(255,255,255,0.85); }
h1,h2,h3,h4 { color:#fff !important; font-family:'Tajawal',sans-serif !important; }

.stTabs [data-baseweb="tab-list"] { background:rgba(255,255,255,0.04) !important; border-radius:18px !important; padding:5px !important; gap:4px !important; border:1px solid rgba(82,183,136,0.15) !important; }
.stTabs [data-baseweb="tab"] { background:transparent !important; border-radius:13px !important; color:#74c69d !important; font-weight:600 !important; font-size:0.95rem !important; padding:10px 20px !important; border:none !important; font-family:'Tajawal',sans-serif !important; transition:all 0.25s !important; }
.stTabs [aria-selected="true"] { background:linear-gradient(135deg,#2d6a4f,#52b788) !important; color:#fff !important; box-shadow:0 4px 16px rgba(82,183,136,0.35) !important; }
.stTabs [data-baseweb="tab-panel"] { padding:22px 0 0 !important; }

.stTextInput > label, .stTextArea > label, .stSelectbox > label,
.stMultiSelect > label, .stNumberInput > label, .stDateInput > label { color:#74c69d !important; font-size:0.9rem !important; font-weight:600 !important; }
.stTextInput > div > div > input, .stTextArea > div > textarea { background:rgba(255,255,255,0.06) !important; border:1.5px solid rgba(82,183,136,0.2) !important; border-radius:12px !important; color:#fff !important; font-family:'Tajawal',sans-serif !important; direction:rtl !important; }
.stTextInput > div > div > input:focus, .stTextArea > div > textarea:focus { border-color:#52b788 !important; box-shadow:0 0 0 3px rgba(82,183,136,0.12) !important; }
.stTextInput > div > div > input::placeholder { color:rgba(255,255,255,0.3) !important; }
.stNumberInput > div > div > input { background:rgba(255,255,255,0.06) !important; border:1.5px solid rgba(82,183,136,0.2) !important; border-radius:12px !important; color:#fff !important; font-family:'Tajawal',sans-serif !important; direction:rtl !important; }
.stSelectbox > div > div, .stMultiSelect > div > div { background:rgba(255,255,255,0.06) !important; border:1.5px solid rgba(82,183,136,0.2) !important; border-radius:12px !important; color:#fff !important; font-family:'Tajawal',sans-serif !important; }
.stDateInput > div > div > input { background:rgba(255,255,255,0.06) !important; border:1.5px solid rgba(82,183,136,0.2) !important; border-radius:12px !important; color:#fff !important; font-family:'Tajawal',sans-serif !important; }
[data-baseweb="tag"] { background:linear-gradient(135deg,#2d6a4f,#52b788) !important; border-radius:8px !important; }

.stButton > button { background:linear-gradient(135deg,#2d6a4f,#52b788) !important; color:#fff !important; border:none !important; border-radius:12px !important; font-family:'Tajawal',sans-serif !important; font-weight:700 !important; transition:all 0.2s !important; box-shadow:0 4px 16px rgba(82,183,136,0.25) !important; }
.stButton > button:hover { transform:translateY(-2px) !important; box-shadow:0 6px 24px rgba(82,183,136,0.4) !important; }
.stButton > button[kind="secondary"] { background:rgba(255,255,255,0.07) !important; border:1.5px solid rgba(82,183,136,0.25) !important; box-shadow:none !important; }

div[data-testid="metric-container"] { background:rgba(255,255,255,0.05) !important; border:1px solid rgba(82,183,136,0.2) !important; border-radius:16px !important; padding:18px !important; direction:rtl; text-align:right; }
div[data-testid="metric-container"] label { color:#74c69d !important; font-size:0.88rem !important; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] { color:#fff !important; font-size:2rem !important; font-weight:800 !important; }
div[data-testid="metric-container"] > div > div:last-child { display:none !important; }

.stExpander { background:rgba(255,255,255,0.04) !important; border:1px solid rgba(82,183,136,0.15) !important; border-radius:16px !important; margin-bottom:10px !important; }
.stExpander > div { background:transparent !important; }
.stAlert { border-radius:12px !important; font-family:'Tajawal',sans-serif !important; direction:rtl !important; }
div[data-testid="stForm"] { background:transparent !important; border:none !important; padding:0 !important; }

.page-header { background:linear-gradient(135deg,rgba(26,71,49,0.9),rgba(45,106,79,0.8),rgba(82,183,136,0.3)); border:1px solid rgba(82,183,136,0.25); border-radius:22px; padding:28px 32px; margin-bottom:24px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:16px; backdrop-filter:blur(10px); box-shadow:0 8px 40px rgba(0,0,0,0.4); }
.page-header-title { color:#fff; font-size:1.9rem; font-weight:900; }
.page-header-sub { color:#74c69d; font-size:0.95rem; margin-top:4px; }
.page-badge { background:linear-gradient(135deg,#52b788,#2d6a4f); color:#fff; border-radius:50px; padding:8px 20px; font-size:0.9rem; font-weight:700; box-shadow:0 4px 16px rgba(82,183,136,0.3); }

.section-title { color:#52b788; font-size:1.1rem; font-weight:800; margin:20px 0 14px; }
.worker-status-pill { display:inline-block; border-radius:50px; padding:3px 14px; font-size:0.82rem; font-weight:700; }
.pill-pending  { background:rgba(255,193,7,0.15); color:#ffd60a; border:1px solid rgba(255,193,7,0.3); }
.pill-approved { background:rgba(82,183,136,0.15); color:#52b788; border:1px solid rgba(82,183,136,0.3); }
.pill-rejected { background:rgba(239,68,68,0.15); color:#f87171; border:1px solid rgba(239,68,68,0.3); }

.completion-bar-wrap { background:rgba(255,255,255,0.08); border-radius:50px; height:10px; overflow:hidden; margin:8px 0; }
.completion-bar-fill { height:100%; border-radius:50px; background:linear-gradient(90deg,#52b788,#2d6a4f); transition:width 0.6s; }

.stat-card { background:rgba(255,255,255,0.05); border:1px solid rgba(82,183,136,0.2); border-radius:18px; padding:20px 16px; text-align:center; transition:transform 0.2s,box-shadow 0.2s; }
.stat-card:hover { transform:translateY(-4px); box-shadow:0 8px 28px rgba(82,183,136,0.2); }
.stat-num { font-size:2.2rem; font-weight:900; color:#52b788; }
.stat-label { font-size:0.85rem; color:rgba(255,255,255,0.5); margin-top:4px; }

.progress-wrap { background:rgba(255,255,255,0.08); border-radius:50px; height:12px; overflow:hidden; margin:14px 0 6px; }
.progress-fill { height:100%; border-radius:50px; background:linear-gradient(90deg,#52b788,#2d6a4f); transition:width 0.8s cubic-bezier(0.16,1,0.3,1); }

.task-card { background:rgba(255,255,255,0.04); border:1.5px solid rgba(255,255,255,0.1); border-radius:18px; padding:20px 22px; margin-bottom:14px; transition:transform 0.2s,box-shadow 0.2s; animation:cardIn 0.5s cubic-bezier(0.16,1,0.3,1) both; }
.task-card:hover { transform:translateY(-3px); box-shadow:0 8px 28px rgba(0,0,0,0.3); }
.task-card-done { background:rgba(82,183,136,0.08) !important; border-color:rgba(82,183,136,0.4) !important; }
.task-card-now  { background:rgba(230,126,34,0.08) !important; border-color:rgba(230,126,34,0.5) !important; box-shadow:0 0 20px rgba(230,126,34,0.15) !important; animation:cardIn 0.5s cubic-bezier(0.16,1,0.3,1) both,nowPulse 3s ease-in-out infinite !important; }
@keyframes nowPulse { 0%,100%{box-shadow:0 0 20px rgba(230,126,34,0.15);} 50%{box-shadow:0 0 32px rgba(230,126,34,0.35);} }
@keyframes cardIn { from{opacity:0;transform:translateY(16px);} to{opacity:1;transform:translateY(0);} }
@keyframes heroIn { from{opacity:0;transform:translateY(-20px);} to{opacity:1;transform:translateY(0);} }
@keyframes float { 0%,100%{transform:translateY(0);} 50%{transform:translateY(-10px);} }
@keyframes shimmer { from{background-position:0% center;} to{background-position:200% center;} }

.task-title-text { color:#fff; font-size:1.08rem; font-weight:800; }
.task-time-text  { color:#52b788; font-size:0.9rem; font-weight:600; margin-top:4px; }
.task-desc-text  { color:rgba(255,255,255,0.65); font-size:0.92rem; line-height:1.6; margin-top:8px; }
.task-desc-done  { color:rgba(255,255,255,0.3); text-decoration:line-through; font-size:0.92rem; margin-top:8px; }
.badge { display:inline-block; border-radius:20px; padding:4px 14px; font-size:0.8rem; font-weight:800; }
.badge-done { background:rgba(82,183,136,0.2); color:#52b788; border:1px solid rgba(82,183,136,0.4); }
.badge-now  { background:rgba(230,126,34,0.2); color:#f0a500; border:1px solid rgba(230,126,34,0.4); }

.rank-row { display:flex; align-items:center; gap:14px; background:rgba(255,255,255,0.04); border:1px solid rgba(82,183,136,0.12); border-radius:14px; padding:12px 18px; margin-bottom:8px; transition:transform 0.2s; }
.rank-row:hover { transform:translateX(-4px); }
.rank-highlight { background:rgba(246,216,96,0.08) !important; border-color:rgba(246,216,96,0.3) !important; }
.rank-num { font-size:1.2rem; font-weight:900; color:#52b788; min-width:36px; }
.rank-name { font-size:1rem; font-weight:700; color:#fff; flex:1; }
.rank-score { font-size:0.88rem; color:#74c69d; font-weight:700; }
.rank-you { font-size:0.78rem; font-weight:700; color:#f6d860; background:rgba(246,216,96,0.15); border:1px solid rgba(246,216,96,0.3); border-radius:20px; padding:2px 10px; }
.medal-badge { display:inline-block; background:linear-gradient(135deg,#f6d860,#f0a500); color:#5a3e00; border-radius:20px; padding:4px 14px; font-size:0.82rem; font-weight:800; margin:2px 3px; box-shadow:0 2px 10px rgba(240,165,0,0.3); }

.hero-header { background:linear-gradient(135deg,rgba(26,71,49,0.95),rgba(45,106,79,0.85),rgba(82,183,136,0.4)); border:1px solid rgba(82,183,136,0.3); border-radius:24px; padding:28px 32px; margin-bottom:24px; backdrop-filter:blur(16px); box-shadow:0 8px 40px rgba(0,0,0,0.4); position:relative; overflow:hidden; animation:heroIn 0.7s cubic-bezier(0.16,1,0.3,1) both; }
.hero-header::before { content:''; position:absolute; top:-60px; left:-60px; width:200px; height:200px; background:radial-gradient(circle,rgba(82,183,136,0.12),transparent 70%); border-radius:50%; }
.hero-header::after  { content:''; position:absolute; bottom:-40px; right:-30px; width:160px; height:160px; background:radial-gradient(circle,rgba(82,183,136,0.08),transparent 70%); border-radius:50%; }
.worker-name { color:#fff; font-size:1.9rem; font-weight:900; margin-bottom:4px; }
.worker-sub  { color:#74c69d; font-size:1rem; margin-bottom:10px; }
.live-clock  { background:rgba(255,255,255,0.12); border:1px solid rgba(82,183,136,0.25); border-radius:14px; padding:10px 20px; color:#fff; font-size:1.15rem; font-weight:800; letter-spacing:1px; backdrop-filter:blur(8px); }

.login-hero { text-align:center; padding:40px 20px 16px; animation:heroIn 0.8s cubic-bezier(0.16,1,0.3,1) both; }
.farm-logo  { display:block; margin:0 auto 16px; filter:drop-shadow(0 8px 28px rgba(82,183,136,0.45)); animation:float 4s ease-in-out infinite; }
.farm-title { font-size:2.6rem; font-weight:900; background:linear-gradient(135deg,#52b788,#95d5b2,#52b788); background-size:200% auto; -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; animation:shimmer 3s linear infinite; margin-bottom:6px; }
.farm-subtitle { color:#74c69d; font-size:1rem; font-weight:500; margin-bottom:24px; }
.card-glass { background:rgba(255,255,255,0.06); backdrop-filter:blur(20px); border:1px solid rgba(82,183,136,0.2); border-radius:24px; padding:32px 28px; margin:0 auto 20px; max-width:520px; box-shadow:0 8px 40px rgba(0,0,0,0.3); }
.success-banner { background:linear-gradient(135deg,#1a4731,#2d6a4f,#52b788); border-radius:18px; padding:28px 22px; text-align:center; box-shadow:0 8px 32px rgba(26,71,49,0.4); border:1px solid rgba(82,183,136,0.4); }
.footer-text { text-align:center; color:rgba(116,198,157,0.4); font-size:0.8rem; margin-top:28px; padding-bottom:20px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  صفحة تسجيل الدخول
# ─────────────────────────────────────────────
def page_login():
    col_c = st.columns([1, 2, 1])[1]
    with col_c:
        st.markdown("""
        <div class="login-hero">
        <svg class="farm-logo" width="110" height="90" viewBox="0 0 110 90" xmlns="http://www.w3.org/2000/svg">
          <rect x="72" y="6" width="6" height="18" rx="3" fill="#74c69d"/>
          <ellipse cx="75" cy="6" rx="3" ry="2" fill="#52b788"/>
          <rect x="52" y="22" width="38" height="22" rx="5" fill="#2d6a4f"/>
          <rect x="55" y="25" width="32" height="16" rx="3" fill="#3a8f68"/>
          <rect x="24" y="28" width="34" height="26" rx="5" fill="#1a4731"/>
          <rect x="28" y="31" width="26" height="16" rx="3" fill="rgba(82,183,136,0.22)" stroke="#52b788" stroke-width="1.2"/>
          <rect x="56" y="34" width="6" height="14" fill="#2d6a4f"/>
          <rect x="24" y="50" width="66" height="8" rx="3" fill="#1a4731"/>
          <circle cx="40" cy="68" r="21" fill="none" stroke="#2d6a4f" stroke-width="7"/>
          <circle cx="40" cy="68" r="13" fill="#1a4731"/>
          <circle cx="40" cy="68" r="5" fill="#52b788"/>
          <line x1="40" y1="55" x2="40" y2="47" stroke="#52b788" stroke-width="2" stroke-linecap="round"/>
          <line x1="40" y1="81" x2="40" y2="89" stroke="#52b788" stroke-width="2" stroke-linecap="round"/>
          <line x1="27" y1="68" x2="19" y2="68" stroke="#52b788" stroke-width="2" stroke-linecap="round"/>
          <line x1="53" y1="68" x2="61" y2="68" stroke="#52b788" stroke-width="2" stroke-linecap="round"/>
          <circle cx="84" cy="72" r="12" fill="none" stroke="#2d6a4f" stroke-width="5"/>
          <circle cx="84" cy="72" r="6" fill="#1a4731"/>
          <circle cx="84" cy="72" r="2.5" fill="#52b788"/>
          <circle cx="89" cy="38" r="3.5" fill="#95d5b2" opacity="0.8"/>
        </svg>
        <div class="farm-title">مزرعة الشاوية</div>
        <div class="farm-subtitle">نبقي المزرعة تعمل بسلاسة · منذ الفجر حتى الغروب</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="card-glass">', unsafe_allow_html=True)
        tab1, tab2, tab3 = st.tabs(["دخول العامل", "تسجيل جديد", "دخول المدير"])

        with tab1:
            with st.form("worker_login_form"):
                worker_name = st.text_input("الاسم الكامل", placeholder="أدخل اسمك كما سجّلته")
                password    = st.text_input("كلمة المرور", type="password", placeholder="••••••••")
                submitted   = st.form_submit_button("تسجيل الدخول", use_container_width=True)
                if submitted:
                    if not worker_name or not password:
                        st.error("يرجى إدخال الاسم وكلمة المرور.")
                    else:
                        worker = login_worker(worker_name.strip(), password)
                        if worker:
                            st.session_state.user = worker
                            st.session_state.role = "worker"
                            st.session_state.login_time = datetime.now()
                            if worker["status"] == "approved":
                                st.session_state.page = "worker"
                                st.rerun()
                            elif worker["status"] == "pending":
                                st.warning("طلبك لا يزال قيد المراجعة. انتظر موافقة المدير.")
                            else:
                                st.error("طلبك لم يُقبل. تواصل مع مدير المزرعة.")
                        else:
                            st.error("الاسم أو كلمة المرور غير صحيحة.")

        with tab2:
            with st.form("registration_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1: reg_name  = st.text_input("الاسم الكامل *", placeholder="محمد أحمد")
                with col2: reg_phone = st.text_input("رقم الهاتف *", placeholder="+966 5X XXX XXXX")
                skill_options = ["إدارة الماشية","العمل الزراعي وحقلي","تشغيل المعدات",
                                 "رعاية صحة الحيوانات","أنظمة الري والمياه",
                                 "التسييج والبناء","عمليات الألبان","إدارة الدواجن"]
                col3, col4 = st.columns(2)
                with col3: reg_exp    = st.number_input("سنوات الخبرة *", min_value=0, max_value=50, value=0, step=1)
                with col4: reg_skills = st.multiselect("مجالات الخبرة *", skill_options, placeholder="اختر مهاراتك")
                col5, col6 = st.columns(2)
                with col5: reg_pass    = st.text_input("كلمة المرور *", type="password", placeholder="6 أحرف على الأقل")
                with col6: reg_confirm = st.text_input("تأكيد كلمة المرور *", type="password", placeholder="أعد الكتابة")
                reg_submitted = st.form_submit_button("تقديم الطلب", use_container_width=True)
                if reg_submitted:
                    errors = []
                    if not reg_name.strip(): errors.append("الاسم الكامل مطلوب.")
                    if not reg_phone.strip(): errors.append("رقم الهاتف مطلوب.")
                    if not reg_skills: errors.append("يرجى اختيار مهارة واحدة على الأقل.")
                    if len(reg_pass) < 6: errors.append("كلمة المرور يجب أن تكون 6 أحرف على الأقل.")
                    if reg_pass != reg_confirm: errors.append("كلمتا المرور غير متطابقتين.")
                    if errors:
                        for err in errors: st.error(err)
                    else:
                        success, message = register_worker(reg_name.strip(), reg_phone.strip(),
                                                           reg_exp, ", ".join(reg_skills), reg_pass)
                        if success:
                            st.markdown("""
                            <div class="success-banner">
                                <div style="color:#fff;font-size:1.4rem;font-weight:800;margin-bottom:8px;">أهلاً وسهلاً في مزرعة الشاوية!</div>
                                <div style="color:#b7e4c7;font-size:0.95rem;margin-bottom:14px;">تم استلام طلبك. سيُراجعه المدير قريباً.</div>
                                <div style="background:rgba(255,255,255,0.12);border-radius:10px;padding:8px 14px;color:#d8f3dc;font-size:0.88rem;">نتطلع لانضمامك لعائلة المزرعة</div>
                            </div>""", unsafe_allow_html=True)
                        else:
                            st.error(message)

        with tab3:
            with st.form("admin_login_form"):
                username    = st.text_input("اسم