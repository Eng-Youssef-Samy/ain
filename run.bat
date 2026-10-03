@echo off
chcp 65001 >nul
echo جاري تثبيت المكتبات...
pip install -r requirements.txt
echo جاري تشغيل عين...
streamlit run app.py
pause
