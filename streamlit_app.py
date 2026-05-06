import streamlit as st
from datetime import datetime

# --- إعدادات الصفحة الأصلية ---
st.set_page_config(page_title="مزرعة الشاوية", page_icon="🚜", layout="wide")

# --- محاكي قاعدة البيانات ---
if 'users' not in st.session_state:
    st.session_state.users = {"admin": {"password": "farm123", "role": "admin"}}
if 'pending_users' not in st.session_state:
    st.session_state.pending_users = {}
if 'worker_data' not in st.session_state:
    st.session_state.worker_data = {}

# --- وظيفة صفحة العامل (حيث كان الخطأ) ---
def page_worker():
    st.title("صفحة العامل")
    worker_name = st.session_state.get("username")
    
    if st.button("تسجيل الخروج"):
        st.session_state.page = "login"
        st.rerun()

    st.write(f"أهلاً بك يا {worker_name}")
    
    # تصليح الخطأ هنا: التأكد من أن القيم وقتية قبل الحساب
    if st.button("تسجيل بداية العمل"):
        st.session_state.worker_data[worker_name] = datetime.now()
        st.success("تم تسجيل وقت البدء.")

    if worker_name in st.session_state.worker_data:
        start_time = st.session_state.worker_data[worker_name]
        now = datetime.now()
        # الإصلاح الجذري للسطر 678:
        duration = now - start_time
        duration_minutes = int(duration.total_seconds() // 60)
        st.info(f"أنت تعمل منذ: {duration_minutes} دقيقة")

# --- وظيفة صفحة المدير ---
def page_admin():
    st.title("لوحة تحكم المدير")
    if st.button("تسجيل الخروج"):
        st.session_state.page = "login"
        st.rerun()
    
    st.subheader("طلبات الانضمام المعلقة")
    for user, info in list(st.session_state.pending_users.items()):
        col1, col2 = st.columns([3, 1])
        col1.write(f"العامل: {user}")
        if col2.button("قبول", key=user):
            st.session_state.users[user] = {"password": info["password"], "role": "worker"}
            del st.session_state.pending_users[user]
            st.rerun()

# --- صفحة تسجيل الدخول ---
def page_login():
    st.title("مزرعة الشاوية - تسجيل الدخول")
    
    tab1, tab2 = st.tabs(["دخول", "تسجيل جديد"])
    
    with tab1:
        u = st.text_input("اسم المستخدم")
        p = st.text_input("كلمة المرور", type="password")
        if st.button("دخول"):
            if u in st.session_state.users and st.session_state.users[u]["password"] == p:
                st.session_state.username = u
                st.session_state.role = st.session_state.users[u]["role"]
                st.session_state.page = st.session_state.role
                st.rerun()
            else:
                st.error("بيانات خاطئة")
                
    with tab2:
        new_u = st.text_input("اسم مستخدم جديد")
        new_p = st.text_input("كلمة مرور جديدة", type="password")
        if st.button("إرسال طلب"):
            st.session_state.pending_users[new_u] = {"password": new_p}
            st.info("تم إرسال الطلب للمدير")

# --- التوجيه بين الصفحات (الأسطر الأخيرة التي أرسلتها في الصورة) ---
if "page" not in st.session_state:
    st.session_state.page = "login"

if st.session_state.page == "admin":
    page_admin()
elif st.session_state.page == "worker":
    page_worker()
else:
    page_login()
