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
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DB = os.getenv("PG_DB", "taktak_db")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "your_password")

# ==================== إعدادات النظام ====================
SUPPORTED_CITIES = ['الرياض', 'جدة']
MAX_SEATS = 8
MIN_SEATS = 1
