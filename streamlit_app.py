import streamlit as st
import pandas as pd
from datetime import datetime

# إعدادات الصفحة لتظهر بشكل احترافي
st.set_page_config(page_title="نظام إدارة المزرعة", layout="wide", initial_sidebar_state="expanded")

# التنسيق الجمالي (CSS) ليشبه الواجهة التي كانت في ريبلت
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stCard { border-radius: 15px; border: 1px solid #e0e0e0; padding: 20px; background-color: white; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .points-box { background-color: #fff9db; border: 1px solid #fab005; padding: 10px; border-radius: 10px; text-align: center; }
    div.stButton > button { width: 100%; border-radius: 10px; background-color: #4CAF50; color: white; }
    </style>
    """, unsafe_allow_html=True)

# محاكاة قاعدة البيانات (هنا نضع بيانات الـ 750 خروف والعمال)
if 'worker_points' not in st.session_state:
    st.session_state.worker_points = 1250  # نقاط العامل الحالية
if 'tasks' not in st.session_state:
    st.session_state.tasks = [
        {"id": 1, "title": "تلقيح خراف السردي", "priority": "عالية", "points": 50, "status": "قيد التنفيذ"},
        {"id": 2, "title": "تنظيف الحظيرة رقم 3", "priority": "متوسطة", "points": 25, "status": "انتظار"}
    ]

# القائمة الجانبية
st.sidebar.title("🚜 قائمة التحكم")
choice = st.sidebar.radio("انتقل إلى:", ["لوحة القيادة (المدير)", "لوحة العمال", "إحصائيات الخراف"])

# 1. لوحة القيادة (Manager Dashboard)
if choice == "لوحة القيادة (المدير)":
    st.title("📊 لوحة القيادة")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("إجمالي العمال", "12")
    with col2:
        st.metric("مهام مكتملة", "45", "+5")
    with col3:
        st.metric("خراف السردي", "500")
    with col4:
        st.metric("خراف الدمان", "250")

    st.subheader("📝 موجز المهام الجارية")
    df_tasks = pd.DataFrame(st.session_state.tasks)
    st.table(df_tasks)

# 2. لوحة العمال (Worker Board)
elif choice == "لوحة العمال":
    st.title("👷 لوحة مهام العمال")
    
    # عرض النقاط والميداليات
    col_p1, col_p2 = st.columns([1, 3])
    with col_p1:
        st.markdown(f"""<div class="points-box">
            <h3 style="margin:0;">🏆 {st.session_state.worker_points}</h3>
            <p style="margin:0;">نقطة مكتسبة</p>
        </div>""", unsafe_allow_html=True)
    
    st.subheader("⚡ المهام الحالية")
    for task in st.session_state.tasks:
        with st.expander(f"📌 {task['title']} - ({task['points']} نقطة)"):
            st.write(f"الأولوية: {task['priority']}")
            if st.button(f"إتمام المهمة: {task['title']}", key=task['id']):
                st.success("تم إرسال المهمة للمراجعة!")

# 3. إحصائيات الخراف (Sheep Inventory)
elif choice == "إحصائيات الخراف":
    st.title("🐑 إحصائيات القطيع")
    st.info("هنا يمكنك متابعة أعداد السردي والدمان والمبيعات المتوقعة.")
    # يمكن إضافة جداول البيانات هنا لاحقاً
