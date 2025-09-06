import os

# ==================== إعدادات تليجرام ====================
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

# ==================== إعدادات قاعدة البيانات ====================
PG_HOST = os.getenv('PG_HOST', 'localhost')
PG_PORT = os.getenv('PG_PORT', '5432')
PG_DB = os.getenv('PG_DB', 'taktak_db')
PG_USER = os.getenv('PG_USER', 'postgres')
PG_PASSWORD = os.getenv('PG_PASSWORD', 'your_password')

# ==================== إعدادات النظام ====================
SUPPORTED_CITIES = ['الرياض', 'جدة']
MAX_RATING = 5
MIN_RATING = 1
