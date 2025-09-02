"""
ملف إعدادات نظام طقطق
"""
import os
from dotenv import load_dotenv

# تحميل متغيرات البيئة من .env (يشتغل محليًا فقط)
load_dotenv()

# ==================== إعدادات تليجرام ====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ==================== إعدادات قاعدة البيانات ====================
 host=os.getenv("PGHOST"),
    port=os.getenv("PGPORT"),
    dbname=os.getenv("PGDATABASE"),
    user=os.getenv("PGUSER"),
    password=os.getenv("PGPASSWORD")

# ==================== إعدادات النظام ====================
SUPPORTED_CITIES = ['الرياض', 'جدة']
MAX_SEATS = 8
MIN_SEATS = 1
