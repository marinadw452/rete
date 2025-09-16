import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

# ==================== إعدادات قاعدة البيانات ====================
PG_HOST = os.getenv("PGHOST")
PG_PORT = os.getenv("PGPORT")
PG_DB = os.getenv("PGDATABASE")
PG_USER = os.getenv("PGUSER")
PG_PASSWORD = os.getenv("PGPASSWORD")

# ==================== إعدادات النظام ====================
SUPPORTED_CITIES = ['الرياض', 'جدة']
MAX_RATING = 5
MIN_RATING = 1
