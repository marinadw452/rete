import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage


from config import BOT_TOKEN
from database import init_db
from handlers import start_handlers, client_handlers, captain_handlers
from handlers import matching_handlers

# إنشاء الجداول عند أول تشغيل
init_db()

# تهيئة البوت و Dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# تسجيل الـ handlers
start_handlers.register_handlers(dp)
client_handlers.register_handlers(dp)
captain_handlers.register_handlers(dp)
matching_handlers.register_handlers(dp)
print("🤖 البوت يعمل الآن!")

if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
