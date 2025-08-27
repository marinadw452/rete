import asyncio
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import BOT_TOKEN
from database import init_db, save_user, find_captains, update_match
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

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
    neigh = callback.data.split("_")[1]
    await state.update_data(neighborhood=neigh)
    data = await state.get_data()

    await state.update_data(city=city, neighborhood=neighborhood)
await callback.message.answer("✅ تم حفظ بياناتك بنجاح!")
# هنا فقط إذا كانت كل البيانات موجودة
user_data = await state.get_data()
if all(k in user_data for k in ["name", "phone", "role", "subscription", "city", "neighborhood"]):
    save_user(callback.from_user.id, user_data)


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

# ========== العميل يختار كابتن ==========
@router.callback_query(F.data.startswith("choose_captain:"))
async def handle_choose_captain(callback: CallbackQuery):
    captain_id = int(callback.data.split(":")[1])
    client_id = callback.from_user.id

    cursor.execute(
        "SELECT name, phone, city, neighborhood, subscription FROM users WHERE user_id = %s",
        (client_id,)
    )
    client = cursor.fetchone()

    if not client:
        await callback.message.answer("❌ لم يتم العثور على بياناتك.")
        return

    client_name, client_phone, city, neighborhood, subscription = client

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ موافق", callback_data=f"accept_client:{client_id}")],
        [InlineKeyboardButton(text="❌ رفض", callback_data=f"reject_client:{client_id}")]
    ])

    await bot.send_message(
        captain_id,
        f"🚗 لديك طلب جديد من عميل:\n\n"
        f"👤 الاسم: {client_name}\n"
        f"📞 الجوال: {client_phone}\n"
        f"🏙️ المدينة: {city}\n"
        f"📍 الحي: {neighborhood}\n"
        f"💳 الاشتراك: {subscription}\n\n"
        "هل ترغب بقبول الطلب؟",
        reply_markup=kb
    )

    await callback.answer("✅ تم إرسال الطلب للكابتن، بانتظار رده.")


# ========== الكابتن يوافق ==========
@router.callback_query(F.data.startswith("accept_client:"))
async def accept_client(callback: CallbackQuery):
    client_id = int(callback.data.split(":")[1])
    captain_id = callback.from_user.id

    # تحديث حالة الكابتن
    cursor.execute("UPDATE users SET available = FALSE WHERE user_id = %s", (captain_id,))
    conn.commit()

    # حفظ المطابقة
    cursor.execute(
        "INSERT INTO matches (client_id, captain_id, status) VALUES (%s, %s, %s)",
        (client_id, captain_id, "accepted")
    )
    conn.commit()

    await bot.send_message(client_id, "✅ الكابتن وافق على طلبك! سيتم التواصل معك 🚕")
    await callback.message.edit_text("✅ تم قبول الطلب وإشعار العميل.")


# ========== الكابتن يرفض ==========
@router.callback_query(F.data.startswith("reject_client:"))
async def reject_client(callback: CallbackQuery):
    client_id = int(callback.data.split(":")[1])
    captain_id = callback.from_user.id

    # حفظ الرفض
    cursor.execute(
        "INSERT INTO matches (client_id, captain_id, status) VALUES (%s, %s, %s)",
        (client_id, captain_id, "rejected")
    )
    conn.commit()

    await bot.send_message(client_id, "❌ الكابتن رفض طلبك. جرب كابتن آخر.")
    await callback.message.edit_text("❌ تم رفض الطلب.")


# ================== Main ==================
if __name__ == "__main__":
    init_db()
    asyncio.run(dp.start_polling(bot))


