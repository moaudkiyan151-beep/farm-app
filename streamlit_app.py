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
    c.execute("DELETE FROM task_complet
