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
                username    = st.text_input("اسم المستخدم", placeholder="admin")
                adm_pass    = st.text_input("كلمة المرور", type="password", placeholder="••••••••")
                adm_submit  = st.form_submit_button("الدخول كمدير", use_container_width=True)
                if adm_submit:
                    admin_user, admin_hash = get_admin_credentials()
                    if username == admin_user and hash_password(adm_pass) == admin_hash:
                        st.session_state.user = {"name": "المدير"}
                        st.session_state.role = "admin"
                        st.session_state.page = "admin"
                        st.rerun()
                    else:
                        st.error("بيانات المدير غير صحيحة.")

        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="footer-text">مزرعة الشاوية — من الفجر حتى الغروب</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  لوحة تحكم المدير
# ─────────────────────────────────────────────
def page_admin():
    st.markdown("""
    <div class="page-header">
        <div>
            <div class="page-header-title">لوحة تحكم المدير</div>
            <div class="page-header-sub">إدارة عمال ومهام مزرعة الشاوية</div>
        </div>
        <div class="page-badge">مزرعة الشاوية</div>
    </div>""", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["طلبات العمال", "إدارة المهام", "حالة الإنجاز", "إعدادات الحساب"])

    with tab1:
        workers  = get_all_workers()
        pending  = [w for w in workers if w["status"] == "pending"]
        approved = [w for w in workers if w["status"] == "approved"]
        rejected = [w for w in workers if w["status"] == "rejected"]
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("إجمالي الطلبات", len(workers))
        col_m2.metric("قيد المراجعة",   len(pending))
        col_m3.metric("مقبولون",         len(approved))
        col_m4.metric("مرفوضون",         len(rejected))
        st.markdown("<br>", unsafe_allow_html=True)

        status_map   = {"الكل":"all","قيد المراجعة":"pending","مقبول":"approved","مرفوض":"rejected"}
        filter_label = st.selectbox("تصفية حسب الحالة", list(status_map.keys()), index=0)
        filter_status = status_map[filter_label]
        display_workers = workers if filter_status == "all" else [w for w in workers if w["status"] == filter_status]

        if not display_workers:
            st.info("لا توجد طلبات في هذه الفئة.")
        else:
            for w in display_workers:
                status    = w["status"]
                status_ar = {"pending":"قيد المراجعة","approved":"مقبول","rejected":"مرفوض"}.get(status, status)
                pill      = {"pending":"pill-pending","approved":"pill-approved","rejected":"pill-rejected"}.get(status,"")
                with st.expander(f"{w['name']} — {w['applied_at'][:10]}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"**الاسم:** {w['name']}")
                        st.markdown(f"**الهاتف:** {w['phone']}")
                    with c2:
                        st.markdown(f"**سنوات الخبرة:** {w['experience_years']}")
                        st.markdown(f"**المهارات:** {w['skills']}")
                    st.markdown(f"الحالة: <span class='worker-status-pill {pill}'>{status_ar}</span>", unsafe_allow_html=True)
                    if w.get("notes"): st.info(f"ملاحظات المدير: {w['notes']}")

                    if status == "pending":
                        note = st.text_input("ملاحظات اختيارية", key=f"notes_{w['id']}", placeholder="مثال: خلفية ممتازة")
                        ca, cr, _ = st.columns([1,1,3])
                        with ca:
                            if st.button("قبول", key=f"approve_{w['id']}", type="primary"):
                                update_worker_status(w["id"], "approved", note)
                                st.success(f"تم قبول {w['name']}!"); st.rerun()
                        with cr:
                            if st.button("رفض", key=f"reject_{w['id']}", type="secondary"):
                                update_worker_status(w["id"], "rejected", note)
                                st.warning(f"تم رفض {w['name']}."); st.rerun()

                    elif status == "approved":
                        medal_options = ["نجم المزرعة","الأسرع إنجازاً","الأكثر التزاماً",
                                         "خبير المواشي","خبير المعدات","خبير الري",
                                         "خبير الدواجن","خبير الألبان","العامل المثالي",
                                         "الروح الجماعية","الأداء المتميز"]
                        current_medals = [m.strip() for m in (w.get("medals") or "").split(",") if m.strip()]
                        st.markdown("**ميداليات المهارات:**")
                        new_medals = st.multiselect("اختر الميداليات", medal_options,
                                                    default=[m for m in current_medals if m in medal_options],
                                                    key=f"medals_{w['id']}")
                        csm, crv = st.columns(2)
                        with csm:
                            if st.button("حفظ الميداليات", key=f"save_medals_{w['id']}", type="primary"):
                                update_worker_medals(w["id"], ", ".join(new_medals))
                                st.success("تم حفظ الميداليات!"); st.rerun()
                        with crv:
                            if st.button("سحب القبول", key=f"revoke_{w['id']}", type="secondary"):
                                update_worker_status(w["id"], "pending", ""); st.rerun()

                    elif status == "rejected":
                        if st.button("إعادة للمراجعة", key=f"reconsider_{w['id']}", type="secondary"):
                            update_worker_status(w["id"], "pending", ""); st.rerun()

    with tab2:
        st.markdown('<div class="section-title">إضافة مهمة جديدة</div>', unsafe_allow_html=True)
        with st.form("add_task_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1: task_title = st.text_input("عنوان المهمة *", placeholder="مثال: رعي الأغنام صباحاً")
            with c2: task_date  = st.date_input("تاريخ المهمة *", value=date.today())
            task_desc = st.text_area("الوصف *", placeholder="اشرح ما يجب على العمال فعله...")
            c3, c4 = st.columns(2)
            with c3: time_slot = st.text_input("الفترة الزمنية *", placeholder="مثال: 06:00 - 08:00 ص")
            with c4:
                approved_ws   = [w for w in get_all_workers() if w["status"] == "approved"]
                assign_opts   = {"جميع العمال": "all"}
                for w in approved_ws: assign_opts[w["name"]] = str(w["id"])
                assigned_label = st.selectbox("تعيين إلى *", list(assign_opts.keys()))
            task_submitted = st.form_submit_button("إضافة المهمة", use_container_width=True)
            if task_submitted:
                errs = []
                if not task_title.strip(): errs.append("عنوان المهمة مطلوب.")
                if not task_desc.strip(): errs.append("وصف المهمة مطلوب.")
                if not time_slot.strip(): errs.append("الفترة الزمنية مطلوبة.")
                if errs:
                    for e in errs: st.error(e)
                else:
                    add_task(task_title.strip(), task_desc.strip(), time_slot.strip(),
                             assign_opts[assigned_label], str(task_date))
                    st.success(f"تمت إضافة المهمة '{task_title}' بنجاح!"); st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-title">جميع المهام</div>', unsafe_allow_html=True)
        tasks = get_tasks()
        if not tasks:
            st.info("لا توجد مهام بعد.")
        else:
            for task in tasks:
                asgn = task["assigned_to"]
                asgn_label = "جميع العمال" if asgn == "all" else (get_worker_by_id(int(asgn)) or {}).get("name", f"عامل #{asgn}")
                completions = get_completions_for_task(task["id"])
                done_badge  = f"{len(completions)} أنجزوا" if completions else "لم ينجز أحد"
                with st.expander(f"{task['title']} — {task['time_slot']} | {task['task_date']} | {done_badge}"):
                    ct1, ct2 = st.columns(2)
                    with ct1:
                        st.markdown(f"**الفترة:** {task['time_slot']}")
                        st.markdown(f"**التاريخ:** {task['task_date']}")
                    with ct2:
                        st.markdown(f"**مُعيَّن إلى:** {asgn_label}")
                    st.markdown(f"**الوصف:** {task['description']}")
                    if completions:
                        st.markdown("**منجزون:**")
                        for c in completions: st.markdown(f"- **{c['name']}** — {c['completed_at']}")
                    else:
                        st.caption("لم ينجز أي عامل هذه المهمة بعد.")
                    if st.button("حذف المهمة", key=f"del_{task['id']}", type="secondary"):
                        delete_task(task["id"]); st.rerun()

    with tab3:
        st.markdown('<div class="section-title">نظرة شاملة على الإنجاز</div>', unsafe_allow_html=True)
        all_completions      = get_all_completions()
        all_tasks            = get_tasks()
        all_workers_approved = [w for w in get_all_workers() if w["status"] == "approved"]
        if not all_workers_approved:
            st.info("لا يوجد عمال مقبولون حتى الآن.")
        else:
            total_tasks = len(all_tasks)
            cs1, cs2, cs3 = st.columns(3)
            cs1.metric("إجمالي المهام", total_tasks)
            cs2.metric("إجمالي الإنجازات", len(all_completions))
            cs3.metric("مهام أُنجزت", len(set(c["task_id"] for c in all_completions)))
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="section-title">إنجاز كل عامل</div>', unsafe_allow_html=True)
            for w in all_workers_approved:
                worker_done = [(c["task_title"], c["completed_at"]) for c in all_completions if c["worker_id"] == w["id"]]
                done_count  = len(worker_done)
                pct         = int(done_count / total_tasks * 100) if total_tasks > 0 else 0
                with st.expander(f"{w['name']} — {done_count}/{total_tasks} مهمة ({pct}%)"):
                    st.markdown(f'<div class="completion-bar-wrap"><div class="completion-bar-fill" style="width:{pct}%;"></div></div><div style="color:#74c69d;font-size:0.85rem;font-weight:700;">{pct}٪ منجز</div>', unsafe_allow_html=True)
                    if done_count == 0:
                        st.caption("لم ينجز هذا العامل أي مهمة بعد.")
                    else:
                        for title, at in worker_done: st.markdown(f"- **{title}** — {at}")

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="section-title">إنجاز كل مهمة</div>', unsafe_allow_html=True)
            today_str    = datetime.now().strftime("%Y-%m-%d")
            today_tasks  = [t for t in all_tasks if t["task_date"] == today_str]
            display_tasks = today_tasks if today_tasks else all_tasks
            for task in display_tasks:
                completions = get_completions_for_task(task["id"])
                done_names  = [c["name"] for c in completions]
                asgn        = task["assigned_to"]
                if asgn == "all":
                    eligible = all_workers_approved
                else:
                    ew = get_worker_by_id(int(asgn))
                    eligible = [ew] if ew else []
                total_el = len(eligible)
                done_c   = len(done_names)
                pct      = int(done_c / total_el * 100) if total_el > 0 else 0
                label    = "مكتملة" if done_c == total_el and total_el > 0 else ("جارية" if done_c > 0 else "معلقة")
                with st.expander(f"{task['title']} — {done_c}/{total_el} ({pct}%) — {label}"):
                    st.markdown(f'<div class="completion-bar-wrap"><div class="completion-bar-fill" style="width:{pct}%;"></div></div>', unsafe_allow_html=True)
                    st.markdown(f"**{task['time_slot']}** | **{task['task_date']}**")
                    if done_names:
                        st.markdown("**أنجزوا:**")
                        for name in done_names:
                            ct = next((c["completed_at"] for c in completions if c["name"] == name), "")
                            st.markdown(f"- {name} — {ct}")
                    pending_names = [w["name"] for w in eligible if w["name"] not in done_names]
                    if pending_names:
                        st.markdown("**لم ينجزوا بعد:**")
                        for name in pending_names: st.markdown(f"- {name}")

    with tab4:
        st.markdown('<div class="section-title">تغيير بيانات المدير</div>', unsafe_allow_html=True)
        current_admin_user, _ = get_admin_credentials()
        st.info(f"اسم المستخدم الحالي: **{current_admin_user}**")
        with st.form("change_credentials_form", clear_on_submit=True):
            current_pass = st.text_input("كلمة المرور الحالية *", type="password", placeholder="للتحقق من هويتك")
            c1, c2 = st.columns(2)
            with c1: new_username = st.text_input("اسم المستخدم الجديد", placeholder="اتركه فارغاً للإبقاء على الحالي")
            with c2: new_pass     = st.text_input("كلمة المرور الجديدة *", type="password", placeholder="6 أحرف على الأقل")
            confirm_new = st.text_input("تأكيد كلمة المرور الجديدة *", type="password", placeholder="أعد الكتابة")
            save_btn = st.form_submit_button("حفظ التغييرات", use_container_width=True)
            if save_btn:
                errors = []
                if not current_pass: errors.append("كلمة المرور الحالية مطلوبة.")
                elif not verify_admin_password(current_pass): errors.append("كلمة المرور الحالية غير صحيحة.")
                if not new_pass: errors.append("كلمة المرور الجديدة مطلوبة.")
                elif len(new_pass) < 6: errors.append("كلمة المرور يجب أن تكون 6 أحرف على الأقل.")
                elif new_pass != confirm_new: errors.append("كلمتا المرور الجديدة غير متطابقتين.")
                if errors:
                    for e in errors: st.error(e)
                else:
                    final_user = new_username.strip() if new_username.strip() else current_admin_user
                    update_admin_credentials(final_user, new_pass)
                    st.success("تم تحديث بيانات الدخول بنجاح!")
                    st.warning("ستحتاج إلى تسجيل الدخول مجدداً بالبيانات الجديدة.")
                    st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("تسجيل الخروج", type="secondary", key="admin_logout"):
        st.session_state.user = None
        st.session_state.role = None
        st.session_state.page = "login"
        st.rerun()
    st.markdown('<div class="footer-text">مزرعة الشاوية — من الفجر حتى الغروب</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  لوحة مهام العامل
# ─────────────────────────────────────────────
def page_worker():
    worker = st.session_state.get("user")
    if worker["status"] == "pending":
        st.warning("طلبك لا يزال قيد المراجعة. ستتمكن من رؤية مهامك بمجرد قبول طلبك.")
        if st.button("تسجيل الخروج", type="secondary"):
            st.session_state.clear(); st.rerun()
        return
    elif worker["status"] == "rejected":
        st.error("طلبك لم يُقبل. يرجى التواصل مع مدير المزرعة.")
        if st.button("تسجيل الخروج", type="secondary"):
            st.session_state.clear(); st.rerun()
        return

    TZ_PLUS1 = timezone(timedelta(hours=1))
    now  = datetime.now(TZ_PLUS1)
    hour = now.hour
    if 5 <= hour < 12: greeting, period = "صباح الخير", "صباحاً"
    elif 12 <= hour < 20: greeting, period = "مساء الخير", "مساءً"
    else: greeting, period = "مساء النور", "مساءً"

    if "login_time" not in st.session_state or st.session_state.login_time is None:
        st.session_state.login_time = now

try:
    session_minutes = int((now - st.session_state.login_time).total_seconds() // 60)
except:
    session_minutes = 0

# تعريف البيانات خارج بلوك except لضمان عملها في كل الحالات
worker = st.session_state.get("user", {})
medals_list = [m.strip() for m in (worker.get("medals", "") or "").split(",") if m.strip()]
medals_html = "".join([f'<span class="medal-badge">{m}</span>' for m in medals_list])
medals_section = f'<div style="margin-top:10px;display:flex;flex-wrap:wrap;gap:4px;">{medals_html}</div>' if medals_html else ""
first_name = worker.get("name", "مستخدم").split()[0]
time_display = now.strftime("%I:%M %p").replace("AM", "ص").replace("PM", "م")

st.markdown(f"""
<div class="hero-header">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;position:relative;z-index:1;">
    <div>
      <div class="worker-name">{greeting}، {first_name}</div>
      <div class="worker-sub">مرحباً بك في لوحة مهامك — {period}</div>
      {medals_section}
    </div>
    <div><div class="live-clock">{time_display}</div></div>
  </div>
</div>""", unsafe_allow_html=True)

    tasks = get_tasks(worker_id=worker["id"])
    if not tasks:
        st.markdown('<div style="background:rgba(82,183,136,0.06);border:2px dashed rgba(82,183,136,0.3);border-radius:20px;padding:48px 32px;text-align:center;"><div style="font-size:1.3rem;font-weight:800;color:#52b788;margin-bottom:8px;">لا توجد مهام معيّنة لك حالياً</div><div style="color:rgba(255,255,255,0.45);">استمتع بوقتك!</div></div>', unsafe_allow_html=True)
    else:
        today      = now.strftime("%Y-%m-%d")
        today_tasks = [t for t in tasks if t["task_date"] == today]
        other_tasks  = [t for t in tasks if t["task_date"] != today]
        done_count  = sum(1 for t in today_tasks if is_task_done_by_worker(t["id"], worker["id"]))
        total_today = len(today_tasks)

        if total_today > 0:
            pct = int(done_count / total_today * 100)
            st.markdown(f"""
            <div style="margin-bottom:24px;">
              <div style="display:flex;gap:12px;margin-bottom:14px;">
                <div class="stat-card" style="flex:1;"><div class="stat-num">{total_today}</div><div class="stat-label">مهام اليوم</div></div>
                <div class="stat-card" style="flex:1;"><div class="stat-num" style="color:#52b788;">{done_count}</div><div class="stat-label">تم الإنجاز</div></div>
                <div class="stat-card" style="flex:1;"><div class="stat-num" style="color:#f0a500;">{total_today-done_count}</div><div class="stat-label">متبقية</div></div>
                <div class="stat-card" style="flex:1;"><div class="stat-num" style="color:rgba(255,255,255,0.5);font-size:1.5rem;">{session_minutes}د</div><div class="stat-label">مدة الجلسة</div></div>
              </div>
              <div class="progress-wrap"><div class="progress-fill" style="width:{pct}%;"></div></div>
              <div style="display:flex;justify-content:space-between;color:#74c69d;font-size:0.85rem;font-weight:700;"><span>{pct}٪ منجز</span><span>{done_count} من {total_today}</span></div>
            </div>""", unsafe_allow_html=True)

        def parse_task_hour(time_slot):
            seg = time_slot.split("-")[0].strip()
            m = re.search(r'(\d{1,2}):(\d{2})', seg)
            if not m: return None
            h = int(m.group(1))
            if "ص" in seg: h = 0 if h == 12 else h
            elif "م" in seg or "م" in time_slot: h = h + 12 if h < 12 else h
            return h

        day_names = {"Monday":"الاثنين","Tuesday":"الثلاثاء","Wednesday":"الأربعاء",
                     "Thursday":"الخميس","Friday":"الجمعة","Saturday":"السبت","Sunday":"الأحد"}
        month_names = {"January":"يناير","February":"فبراير","March":"مارس","April":"أبريل",
                       "May":"مايو","June":"يونيو","July":"يوليو","August":"أغسطس",
                       "September":"سبتمبر","October":"أكتوبر","November":"نوفمبر","December":"ديسمبر"}
        date_ar = f"{day_names.get(now.strftime('%A'),'')}، {now.day} {month_names.get(now.strftime('%B'),'')} {now.year}"

        if today_tasks:
            st.markdown(f'<div class="section-title">مهام اليوم — {date_ar}</div>', unsafe_allow_html=True)
            cols_per_row = 2
            for i in range(0, len(today_tasks), cols_per_row):
                row_tasks = today_tasks[i:i+cols_per_row]
                cols = st.columns(cols_per_row)
                for j, task in enumerate(row_tasks):
                    with cols[j]:
                        is_done    = is_task_done_by_worker(task["id"], worker["id"])
                        task_hour  = parse_task_hour(task["time_slot"])
                        is_current = task_hour is not None and abs(task_hour - hour) <= 1
                        if is_done:
                            cc, bh, dh = "task-card task-card-done", '<span class="badge badge-done">منجزة</span>', f'<div class="task-desc-done">{task["description"]}</div>'
                        elif is_current:
                            cc, bh, dh = "task-card task-card-now", '<span class="badge badge-now">جارية الآن</span>', f'<div class="task-desc-text">{task["description"]}</div>'
                        else:
                            cc, bh, dh = "task-card", "", f'<div class="task-desc-text">{task["description"]}</div>'
                        st.markdown(f'<div class="{cc}"><div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;"><div class="task-title-text">{task["title"]}</div>{bh}</div><div class="task-time-text">{task["time_slot"]}</div>{dh}</div>', unsafe_allow_html=True)
                        if not is_done:
                            if st.button("تحديد كمنجز", key=f"done_{task['id']}_{worker['id']}", use_container_width=True, type="primary"):
                                mark_task_done(task["id"], worker["id"]); st.rerun()
                        else:
                            if st.button("إلغاء الإنجاز", key=f"undone_{task['id']}_{worker['id']}", use_container_width=True, type="secondary"):
                                unmark_task_done(task["id"], worker["id"]); st.rerun()
        else:
            st.info("لا توجد مهام مجدولة لهذا اليوم.")

        if other_tasks:
            st.markdown('<div class="section-title">المهام القادمة</div>', unsafe_allow_html=True)
            for task in other_tasks:
                is_done = is_task_done_by_worker(task["id"], worker["id"])
                st.markdown(f'<div class="task-card" style="opacity:0.75;"><div style="display:flex;justify-content:space-between;align-items:center;"><div class="task-title-text">{task["title"]}</div><div style="color:rgba(255,255,255,0.35);font-size:0.85rem;">{task["task_date"]}</div></div><div class="task-time-text">{task["time_slot"]}</div><div class="task-desc-text">{task["description"]}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">ترتيب العمال اليوم</div>', unsafe_allow_html=True)
    all_workers      = get_all_workers()
    approved_workers = [w for w in all_workers if w["status"] == "approved"]
    all_completions  = get_all_completions()
    today_str        = now.strftime("%Y-%m-%d")
    today_done_counts = {}
    for c in all_completions:
        if c["completed_at"][:10] == today_str:
            today_done_counts[c["worker_id"]] = today_done_counts.get(c["worker_id"], 0) + 1
    ranked      = sorted(approved_workers, key=lambda w: today_done_counts.get(w["id"], 0), reverse=True)
    rank_labels = ["الأول","الثاني","الثالث"]
    for idx, rw in enumerate(ranked[:10]):
        label     = rank_labels[idx] if idx < 3 else str(idx+1)
        done      = today_done_counts.get(rw["id"], 0)
        highlight = "rank-highlight" if rw["id"] == worker["id"] else ""
        you_badge = '<span class="rank-you">أنت</span>' if rw["id"] == worker["id"] else ""
        st.markdown(f'<div class="rank-row {highlight}"><div class="rank-num">{label}</div><div class="rank-name">{rw["name"]} {you_badge}</div><div class="rank-score">{done} مهمة</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("تسجيل الخروج", type="secondary", key="worker_logout"):
        st.session_state.clear()
        st.rerun()
    st.markdown('<div class="footer-text">مزرعة الشاوية — من الفجر حتى الغروب</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  التوجيه بين الصفحات
# ─────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "login"

page = st.session_state.get("page", "login")

if page == "admin" and st.session_state.get("role") == "admin":
    page_admin()
elif page == "worker" and st.session_state.get("role") == "worker":
    page_worker()
else:
    st.session_state.page = "login"
    page_login()
