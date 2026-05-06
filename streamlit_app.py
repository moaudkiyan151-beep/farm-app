```python
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
.stTextInput > div > div > input::placeholder {