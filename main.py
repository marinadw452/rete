import asyncio
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import psycopg2
import psycopg2.extras
from config import BOT_TOKEN, PG_DB, PG_USER, PG_PASSWORD, PG_HOST, PG_PORT
from database import update_match
from database import init_db
# ================== قاعدة البيانات ==================
def get_conn():
    return psycopg2.connect(
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        host=PG_HOST,
        port=PG_PORT,
        cursor_factory=psycopg2.extras.RealDictCursor
    )

# ================== تحميل الأحياء ==================
with open("neighborhoods.json", "r", encoding="utf-8") as f:
    neighborhoods_data = json.load(f)

# ================== FSM ==================
class RegisterStates(StatesGroup):
    role = State()
    subscription = State()
    full_name = State()
    phone = State()
    car_model = State()
    car_plate = State()
    seats = State()
    agreement = State()
    city = State()
    neighborhood = State()
    matching = State()

# ================== Keyboards ==================
def start_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🚕 عميل", callback_data="role_client")
    builder.button(text="🧑‍✈️ كابتن", callback_data="role_captain")
    builder.adjust(2)
    return builder.as_markup()

def subscription_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="يومي", callback_data="sub_daily")
    builder.button(text="شهري", callback_data="sub_monthly")
    builder.adjust(2)
    return builder.as_markup()

def agreement_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ موافق", callback_data="agree")
    return builder.as_markup()

def city_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🏙️ الرياض", callback_data="city_الرياض")
    builder.button(text="🌆 جدة", callback_data="city_جدة")
    builder.adjust(1)
    return builder.as_markup()

def neighborhood_keyboard(city):
    builder = InlineKeyboardBuilder()
    for n in neighborhoods_data.get(city, []):
        builder.button(text=n, callback_data=f"neigh_{n}")
    builder.adjust(3)
    return builder.as_markup()

def captain_choice_keyboard(captain_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ قبول", callback_data=f"accept_{captain_id}")
    builder.button(text="❌ رفض", callback_data=f"reject_{captain_id}")
    builder.adjust(2)
    return builder.as_markup()

# ================== Bot setup ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================== Handlers تسجيل المستخدم ==================
@dp.message(F.text == "/start")
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("مرحباً! اختر دورك:", reply_markup=start_keyboard())
    await state.set_state(RegisterStates.role)

# ... (نفس الكود حق الـ handlers اللي كتبته فوق)

@dp.callback_query()
async def captain_decision_handler(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data
    client_id = callback.from_user.id  # العميل الحالي

    if data.startswith("accept_") or data.startswith("reject_"):
        captain_id = int(data.split("_")[1])

        if data.startswith("accept_"):
            update_match(client_id, captain_id, "accepted")
            await callback.message.answer("✅ تم قبول الكابتن، بياناته مرسلة للعميل.")
        else:
            update_match(client_id, captain_id, "rejected")
            await callback.message.answer("❌ تم رفض الكابتن. يمكنك اختيار كابتن آخر.")

# ================== قبول/رفض الكابتن ==================
@dp.callback_query()
async def captain_decision_handler(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data
    client_id = callback.from_user.id  # العميل الحالي

    if data.startswith("accept_") or data.startswith("reject_"):
        captain_id = int(data.split("_")[1])

        if data.startswith("accept_"):
            update_match(client_id, captain_id, "accepted")
            await callback.message.answer("✅ تم قبول الكابتن، بياناته مرسلة للعميل.")
        else:
            update_match(client_id, captain_id, "rejected")
            await callback.message.answer("❌ تم رفض الكابتن. يمكنك اختيار كابتن آخر.")

# ================== Main ==================
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))

