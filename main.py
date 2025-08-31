import asyncio
import json
import psycopg2
import psycopg2.extras
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import BOT_TOKEN, PG_DB, PG_USER, PG_PASSWORD, PG_HOST, PG_PORT

# ================== DB ==================
def get_conn():
    return psycopg2.connect(
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        host=PG_HOST,
        port=PG_PORT,
        cursor_factory=psycopg2.extras.RealDictCursor
    )

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        role VARCHAR(10) NOT NULL,
        subscription VARCHAR(20),
        full_name TEXT,
        phone TEXT,
        car_model TEXT,
        car_plate TEXT,
        seats INT,
        agreement BOOLEAN DEFAULT FALSE,
        city TEXT,
        neighborhood TEXT,
        is_available BOOLEAN DEFAULT TRUE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS matches (
        id SERIAL PRIMARY KEY,
        client_id BIGINT REFERENCES users(user_id),
        captain_id BIGINT REFERENCES users(user_id),
        status VARCHAR(20) DEFAULT 'pending',
        CONSTRAINT unique_match UNIQUE (client_id, captain_id)
    )
    """)

    conn.commit()
    cur.close()
    conn.close()

def save_user(user_id, data):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (user_id, role, subscription, full_name, phone, car_model, car_plate, seats, agreement, city, neighborhood, is_available)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE)
        ON CONFLICT (user_id) DO UPDATE SET
            role=EXCLUDED.role,
            subscription=EXCLUDED.subscription,
            full_name=EXCLUDED.full_name,
            phone=EXCLUDED.phone,
            car_model=EXCLUDED.car_model,
            car_plate=EXCLUDED.car_plate,
            seats=EXCLUDED.seats,
            agreement=EXCLUDED.agreement,
            city=EXCLUDED.city,
            neighborhood=EXCLUDED.neighborhood,
            is_available=TRUE
    """, (
        user_id,
        data.get("role"),
        data.get("subscription"),
        data.get("full_name"),
        data.get("phone"),
        data.get("car_model"),
        data.get("car_plate"),
        data.get("seats"),
        data.get("agreement"),
        data.get("city"),
        data.get("neighborhood"),
    ))
    conn.commit()
    cur.close()
    conn.close()

def find_captains(city, neighborhood):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM users 
        WHERE role='captain' AND is_available=TRUE AND city=%s AND neighborhood=%s
    """, (city, neighborhood))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def update_match(client_id, captain_id, status):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO matches (client_id, captain_id, status)
        VALUES (%s, %s, %s)
        ON CONFLICT (client_id, captain_id) DO UPDATE 
        SET status = EXCLUDED.status
    """, (client_id, captain_id, status))

    if status == "accepted":
        cur.execute("UPDATE users SET is_available=FALSE WHERE user_id=%s", (captain_id,))
    elif status == "rejected":
        cur.execute("UPDATE users SET is_available=TRUE WHERE user_id=%s", (captain_id,))
    elif status == "pending":
        cur.execute("UPDATE users SET is_available=TRUE WHERE user_id=%s", (captain_id,))

    conn.commit()
    cur.close()
    conn.close()

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
    with open("neighborhoods.json", "r", encoding="utf-8") as f:
        neighborhoods_data = json.load(f)
    builder = InlineKeyboardBuilder()
    for n in neighborhoods_data.get(city, []):
        builder.button(text=n, callback_data=f"neigh_{n}")
    builder.adjust(3)
    return builder.as_markup()

def captain_choice_keyboard(captain_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ اختيار الكابتن", callback_data=f"choose_{captain_id}")
    return builder.as_markup()

# ================== Bot setup ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================== Handlers ==================
@dp.message(F.text == "/start")
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("مرحباً! اختر دورك:", reply_markup=start_keyboard())
    await state.set_state(RegisterStates.role)

@dp.callback_query(F.data.startswith("role_"))
async def role_handler(callback: types.CallbackQuery, state: FSMContext):
    role = callback.data.split("_")[1]
    await state.update_data(role=role)
    await callback.message.answer("اختر نوع الاشتراك:", reply_markup=subscription_keyboard())
    await state.set_state(RegisterStates.subscription)

@dp.callback_query(F.data.startswith("sub_"))
async def subscription_handler(callback: types.CallbackQuery, state: FSMContext):
    sub = callback.data.split("_")[1]
    await state.update_data(subscription=sub)
    await callback.message.answer("📛 أدخل اسمك الكامل:")
    await state.set_state(RegisterStates.full_name)

@dp.message(RegisterStates.full_name)
async def full_name_handler(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await message.answer("📱 أدخل رقم جوالك:")
    await state.set_state(RegisterStates.phone)

@dp.message(RegisterStates.phone)
async def phone_handler(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    data = await state.get_data()
    if data.get("role") == "captain":
        await message.answer("🚘 أدخل موديل السيارة:")
        await state.set_state(RegisterStates.car_model)
    else:
        await message.answer("📜 القوانين: الالتزام بأنظمة التوصيل في السعودية.\nاضغط موافق للمتابعة.", reply_markup=agreement_keyboard())
        await state.set_state(RegisterStates.agreement)

@dp.message(RegisterStates.car_model)
async def car_model_handler(message: types.Message, state: FSMContext):
    await state.update_data(car_model=message.text)
    await message.answer("🔢 أدخل رقم اللوحة:")
    await state.set_state(RegisterStates.car_plate)

@dp.message(RegisterStates.car_plate)
async def car_plate_handler(message: types.Message, state: FSMContext):
    await state.update_data(car_plate=message.text)
    await message.answer("🚪 كم عدد المقاعد المتاحة؟")
    await state.set_state(RegisterStates.seats)

@dp.message(RegisterStates.seats)
async def seats_handler(message: types.Message, state: FSMContext):
    await state.update_data(seats=int(message.text))
    await message.answer("📜 القوانين: الالتزام بأنظمة التوصيل في السعودية.\nاضغط موافق للمتابعة.", reply_markup=agreement_keyboard())
    await state.set_state(RegisterStates.agreement)

@dp.callback_query(F.data == "agree")
async def agreement_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(agreement=True)
    await callback.message.answer("🌆 اختر مدينتك:", reply_markup=city_keyboard())
    await state.set_state(RegisterStates.city)

@dp.callback_query(F.data.startswith("city_"))
async def city_handler(callback: types.CallbackQuery, state: FSMContext):
    city = callback.data.split("_")[1]
    await state.update_data(city=city)
    await callback.message.answer("🏘️ اختر الحي:", reply_markup=neighborhood_keyboard(city))
    await state.set_state(RegisterStates.neighborhood)

@dp.callback_query(F.data.startswith("neigh_"))
async def neighborhood_handler(callback: types.CallbackQuery, state: FSMContext):
    neigh = callback.data.replace("neigh_", "")
    await state.update_data(neighborhood=neigh)
    data = await state.get_data()

    save_user(callback.from_user.id, data)

    if data.get("role") == "client":
        captains = find_captains(data["city"], data["neighborhood"])
        if captains:
            for cap in captains:
                await callback.message.answer(
                    f"كابتن متاح: {cap['full_name']} 🚘 {cap['car_model']} ({cap['car_plate']})\nمقاعد: {cap['seats']}",
                    reply_markup=captain_choice_keyboard(cap["user_id"])
                )
        else:
            await callback.message.answer("🚫 لا يوجد كباتن متاحين حالياً.")
    else:
        await callback.message.answer("✅ تم تسجيلك ككابتن. سيتم إشعارك عند اختيارك من عميل.")

    await state.clear()

# ====== العميل يختار كابتن ======
@dp.callback_query(F.data.startswith("choose_"))
async def client_choose_captain(callback: types.CallbackQuery):
    captain_id = int(callback.data.split("_")[1])
    client_id = callback.from_user.id

    update_match(client_id, captain_id, "pending")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT full_name FROM users WHERE user_id=%s", (client_id,))
    client = cur.fetchone()
    cur.close()
    conn.close()

    await bot.send_message(
        captain_id,
        f"🚖 عندك طلب جديد من العميل {client['full_name']}\nهل توافق؟",
        reply_markup=InlineKeyboardBuilder()
            .button(text="✅ قبول", callback_data=f"cap_accept_{client_id}")
            .button(text="❌ رفض", callback_data=f"cap_reject_{client_id}")
            .adjust(2)
            .as_markup()
    )

    await callback.message.answer("⏳ تم إرسال طلبك للكابتن، ننتظر رده...")

# ====== الكابتن يرد ======
@dp.callback_query(F.data.startswith("cap_accept_"))
async def captain_accept(callback: types.CallbackQuery):
    client_id = int(callback.data.split("_")[2])
    captain_id = callback.from_user.id

    update_match(client_id, captain_id, "accepted")
    await bot.send_message(client_id, "✅ الكابتن وافق على طلبك 🎉")
    await callback.message.answer("تم قبول الطلب ✅")

@dp.callback_query(F.data.startswith("cap_reject_"))
async def captain_reject(callback: types.CallbackQuery):
    client_id = int(callback.data.split("_")[2])
    captain_id = callback.from_user.id

    update_match(client_id, captain_id, "rejected")
    await bot.send_message(client_id, "❌ الكابتن رفض الطلب")
    await callback.message.answer("تم رفض الطلب ❌")

# ================== Main ==================
if __name__ == "__main__":
    init_db()
    asyncio.run(dp.start_polling(bot))
