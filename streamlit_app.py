import streamlit as st

# إعدادات النسخة الرسمية الفاخرة Farm-App-v1.1
st.set_page_config(page_title="Farm-App-v1.1", page_icon="🌿", layout="centered")

# تصميم CSS "الفاخر" - تغيير شامل للألوان والخطوط
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
        background-color: #f0f2f6;
    }
    
    .stApp {
        background: linear-gradient(135deg, #111d12 0%, #000000 100%);
    }

    .main-card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        padding: 30px;
        border-radius: 30px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        margin-bottom: 20px;
    }

    .stButton>button {
        background: linear-gradient(90deg, #4CAF50 0%, #2E7D32 100%);
        color: white;
        border: none;
        border-radius: 15px;
        font-weight: bold;
        transition: 0.3s;
        height: 3.5em;
    }

    .stButton>button:hover {
        transform: scale(1.02);
        box-shadow: 0 5px 15px rgba(76, 175, 80, 0.4);
    }

    .stTextInput>div>div>input {
        background-color: rgba(255, 255, 255, 0.07) !important;
        color: white !important;
        border-radius: 12px !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
    }

    h1 { color: #81c784; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); }
    </style>
    """, unsafe_allow_html=True)

# تهيئة البيانات
if 'workers' not in st.session_state: st.session_state.workers = []
if 'waiting' not in st.session_state: st.session_state.waiting = []

# واجهة التطبيق
with st.container():
    st.markdown("<div class='main-card'>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center;'>MAZRAAT ASHAWIYA</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #aaa;'>إدارة ذكية • مشروع 0001 • v1.1</p>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["👤 العمال", "📝 تسجيل", "🔐 المدير"])

    with tab1:
        st.markdown("<br>", unsafe_allow_html=True)
        user = st.text_input("الاسم الكامل", placeholder="أدخل اسمك هنا")
        pwd = st.text_input("كلمة المرور", type="password", placeholder="••••••••")
        if st.button("دخول العمل"):
            found = next((w for w in st.session_state.workers if w['name'] == user and w['pass'] == pwd), None)
            if found: st.success(f"مرحباً بك {user}")
            else: st.error("الحساب غير موجود أو معلق")

    with tab2:
        st.markdown("<br>", unsafe_allow_html=True)
        n_user = st.text_input("اسم جديد")
        n_pwd = st.text_input("كلمة مرور جديدة", type="password")
        if st.button("إرسال طلب الانضمام"):
            if n_user and n_pwd:
                st.session_state.waiting.append({"name": n_user, "pass": n_pwd})
                st.info("تم إرسال الطلب للمراجعة")

    with tab3:
        st.markdown("<br>", unsafe_allow_html=True)
        adm_u = st.text_input("ID المدير")
        adm_p = st.text_input("Passcode", type="password")
        if st.button("دخول لوحة التحكم"):
            if adm_u == "admin" and adm_p == "farm123":
                st.session_state.is_adm = True
            else: st.error("خطأ في البيانات")

        if st.session_state.get('is_adm'):
            st.markdown("---")
            st.markdown("### طلبات جديدة")
            for i, r in enumerate(st.session_state.waiting):
                c1, c2 = st.columns([3, 1])
                c1.write(r['name'])
                if c2.button("قبول", key=f"a_{i}"):
                    st.session_state.workers.append(r)
                    st.session_state.waiting.pop(i)
                    st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<p style='text-align: center; color: #555; font-size: 0.7em;'>DESIGNED BY AI FOR ASHAWIYA FARM</p>", unsafe_allow_html=True)
