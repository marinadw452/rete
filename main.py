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

# ================== Keyboards (Aiogram v3) ==================
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

@dp.callback_query(RegisterStates.role)
async def role_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.data in ["role_client", "role_captain"]:
        await state.update_data(role=callback.data.split("_")[1])
        await callback.message.answer("اختر الاشتراك:", reply_markup=subscription_keyboard())
        await state.set_state(RegisterStates.subscription)

@dp.callback_query(RegisterStates.subscription)
async def subscription_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.data in ["sub_daily", "sub_monthly"]:
        await state.update_data(subscription=callback.data.split("_")[1])
        await callback.message.answer("أدخل اسمك الكامل:")
        await state.set_state(RegisterStates.full_name)

@dp.message(RegisterStates.full_name)
async def full_name_handler(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await message.answer("أدخل رقم جوالك:")
    await state.set_state(RegisterStates.phone)

@dp.message(RegisterStates.phone)
async def phone_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    role = data.get("role")
    await state.update_data(phone=message.text)
    if role == "captain":
        await message.answer("أدخل نوع السيارة:")
        await state.set_state(RegisterStates.car_model)
    else:
        await message.answer("⚖️ يرجى قراءة قوانين التوصيل في السعودية:")
        await message.answer(
            "1. الالتزام بمواعيد التوصيل.\n"
            "2. الحفاظ على سلامة الركاب.\n"
            "3. عدم قبول طلبات مشبوهة.\n"
            "4. احترام القوانين المحلية."
        )
        await message.answer("اضغط موافق للمتابعة:", reply_markup=agreement_keyboard())
        await state.set_state(RegisterStates.agreement)

@dp.message(RegisterStates.car_model)
async def car_model_handler(message: types.Message, state: FSMContext):
    await state.update_data(car_model=message.text)
    await message.answer("أدخل رقم لوحة السيارة:")
    await state.set_state(RegisterStates.car_plate)

@dp.message(RegisterStates.car_plate)
async def car_plate_handler(message: types.Message, state: FSMContext):
    await state.update_data(car_plate=message.text)
    await message.answer("عدد الركاب المتاحين:")
    await state.set_state(RegisterStates.seats)

@dp.message(RegisterStates.seats)
async def seats_handler(message: types.Message, state: FSMContext):
    await state.update_data(seats=int(message.text))
    await message.answer("⚖️ يرجى قراءة قوانين التوصيل في السعودية:")
    await message.answer(
        "1. الالتزام بمواعيد التوصيل.\n"
        "2. الحفاظ على سلامة الركاب.\n"
        "3. عدم قبول طلبات مشبوهة.\n"
        "4. احترام القوانين المحلية."
    )
    await message.answer("اضغط موافق للمتابعة:", reply_markup=agreement_keyboard())
    await state.set_state(RegisterStates.agreement)

# ================== حفظ البيانات والمطابقة ==================
@dp.callback_query(RegisterStates.agreement)
async def agreement_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "agree":
        data = await state.get_data()
        user_id = callback.from_user.id
        role = data.get("role")
        subscription = data.get("subscription")
        full_name = data.get("full_name")
        phone = data.get("phone")
        car_model = data.get("car_model", None)
        car_plate = data.get("car_plate", None)
        seats = data.get("seats", None)

        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (user_id, role, subscription, full_name, phone, car_model, car_plate, seats, is_available)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,TRUE)
            ON CONFLICT (user_id) DO UPDATE
            SET role=EXCLUDED.role,
                subscription=EXCLUDED.subscription,
                full_name=EXCLUDED.full_name,
                phone=EXCLUDED.phone,
                car_model=EXCLUDED.car_model,
                car_plate=EXCLUDED.car_plate,
                seats=EXCLUDED.seats,
                is_available=EXCLUDED.is_available
        """, (user_id, role, subscription, full_name, phone, car_model, car_plate, seats))
        conn.commit()

        await callback.message.answer("✅ تم التسجيل بنجاح!")

        if role == "client":
            await callback.message.answer("اختر مدينتك:", reply_markup=city_keyboard())
            await state.set_state(RegisterStates.city)
        else:
            await callback.message.answer("يمكنك الآن استقبال طلبات العملاء.")
            await state.clear()

        cursor.close()
        conn.close()

# ================== اختيار المدينة والحي ==================
@dp.callback_query(RegisterStates.city)
async def city_handler(callback: types.CallbackQuery, state: FSMContext):
    city = callback.data.split("_")[1]
    await state.update_data(city=city)
    await callback.message.answer(f"اختر الحي في {city}:", reply_markup=neighborhood_keyboard(city))
    await state.set_state(RegisterStates.neighborhood)

# ================== اختيار الحي وعرض الكباتن ==================
@dp.callback_query(RegisterStates.neighborhood)
async def neighborhood_handler(callback: types.CallbackQuery, state: FSMContext):
    neighborhood = callback.data.split("_")[1]
    await state.update_data(neighborhood=neighborhood)

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM users
        WHERE role='captain' AND is_available=TRUE
    """)
    captains = cursor.fetchall()
    cursor.close()
    conn.close()

    if not captains:
        await callback.message.answer("لا يوجد كباتن متاحين الآن. حاول لاحقاً.")
    else:
        for c in captains:
            await callback.message.answer(
                f"{c['full_name']} - {c['phone']}",
                reply_markup=captain_choice_keyboard(c['user_id'])
            )

# ================== قبول/رفض الكابتن ==================
@dp.callback_query()
async def captain_decision_handler(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data
    if data.startswith("accept_") or data.startswith("reject_"):
        captain_id = int(data.split("_")[1])
        conn = get_conn()
        cursor = conn.cursor()

        if data.startswith("accept_"):
            cursor.execute("UPDATE users SET is_available=FALSE WHERE user_id=%s", (captain_id,))
            conn.commit()
            await callback.message.answer("✅ تم قبول الكابتن، بياناته مرسلة للعميل.")
        else:
            await callback.message.answer("❌ تم رفض الكابتن. يمكنك اختيار كابتن آخر.")

        cursor.close()
        conn.close()

# ================== Main ==================
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
