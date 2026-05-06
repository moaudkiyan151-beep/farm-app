import streamlit as st

# 1. إعدادات الصفحة الرسمية لمشروع Farm-App-v1.1
st.set_page_config(page_title="مزرعة الشاوية v1.1", page_icon="🚜", layout="centered")

# 2. تنسيق الواجهة (CSS) لتظهر بشكل احترافي
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stButton>button { width: 100%; border-radius: 10px; background-color: #2e7d32; color: white; height: 3em; }
    h1, h3 { color: #4caf50; text-align: center; }
    .status-box { padding: 20px; border-radius: 10px; background-color: #1e2127; border: 1px solid #2e7d32; }
    </style>
    """, unsafe_allow_html=True)

# 3. تهيئة مخزن البيانات (Session State)
if 'workers_list' not in st.session_state:
    st.session_state.workers_list = []  # العمال المقبولين
if 'waiting_list' not in st.session_state:
    st.session_state.waiting_list = []  # طلبات الانتظار

# 4. رأس الصفحة
st.markdown("<h1>🚜 مزرعة الشاوية</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>نظام إدارة المزرعة الذكي • النسخة v1.1</p>", unsafe_allow_html=True)

# 5. القائمة الرئيسية (Tabs)
tab1, tab2, tab3 = st.tabs(["🔑 دخول العامل", "📝 تسجيل جديد", "⚙️ لوحة المدير"])

# --- قسم دخول العامل ---
with tab1:
    st.subheader("تسجيل دخول الموظفين")
    w_name = st.text_input("الاسم الكامل", key="worker_login_name")
    w_pass = st.text_input("كلمة المرور", type="password", key="worker_login_pass")
    
    if st.button("دخول للمزرعة"):
        # التحقق من وجود العامل في قائمة المقبولين
        worker = next((u for u in st.session_state.workers_list if u['name'] == w_name and u['pass'] == w_pass), None)
        if worker:
            st.success(f"مرحباً {w_name}! تم تسجيل حضورك بنجاح.")
            st.balloons()
        else:
            st.error("الاسم غير موجود أو بانتظار موافقة المدير.")

# --- قسم التسجيل الجديد ---
with tab2:
    st.subheader("طلب انضمام لفريق العمل")
    with st.container():
        new_user = st.text_input("اختر اسماً للتعريف به")
        new_pass = st.text_input("اختر كلمة مرور قوية", type="password")
        if st.button("إرسال طلب التسجيل"):
            if new_user and new_pass:
                st.session_state.waiting_list.append({"name": new_user, "pass": new_pass})
                st.info("تم إرسال طلبك بنجاح. يرجى مراجعة المدير للموافقة.")
            else:
                st.warning("الرجاء إدخال كافة البيانات.")

# --- قسم المدير (بياناتك الخاصة) ---
with tab3:
    st.subheader("لوحة تحكم صاحب المزرعة")
    # بيانات الدخول الخاصة بك التي اتفقنا عليها
    admin_user = st.text_input("اسم المدير")
    admin_pass = st.text_input("كلمة السر", type="password")
    
    if st.button("فتح لوحة التحكم"):
        if admin_user == "admin" and admin_pass == "farm123":
            st.session_state.admin_auth = True
        else:
            st.error("بيانات الدخول خاطئة!")

    # ما يظهر بعد دخول المدير بنجاح
    if st.session_state.get('admin_auth'):
        st.write("---")
        st.success("أهلاً بك يا صاحب المزرعة (مشروع 0001)")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("العمال المقبولين", len(st.session_state.workers_list))
        with col2:
            st.metric("طلبات الانتظار", len(st.session_state.waiting_list))

        st.write("### 📥 طلبات العمال الجدد")
        if not st.session_state.waiting_list:
            st.info("لا توجد طلبات انضمام حالياً.")
        else:
            for i, request in enumerate(st.session_state.waiting_list):
                with st.expander(f"طلب من: {request['name']}"):
                    c1, c2 = st.columns(2)
                    if c1.button("✅ قبول", key=f"accept_{i}"):
                        st.session_state.workers_list.append(request)
                        st.session_state.waiting_list.pop(i)
                        st.rerun()
                    if c2.button("❌ رفض", key=f"reject_{i}"):
                        st.session_state.waiting_list.pop(i)
                        st.rerun()

        st.write("### 👥 قائمة الفريق الحالي")
        for worker in st.session_state.workers_list:
            st.text(f"• {worker['name']}")

# تذييل الصفحة
st.markdown("---")
st.markdown("<p style='text-align: center; font-size: 0.8em;'>جميع الحقوق محفوظة لمزرعة الشاوية 2026</p>", unsafe_allow_html=True)
