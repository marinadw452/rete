import asyncio
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import BOT_TOKEN
from database import init_db, save_user, find_captains, update_match

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
    neigh = callback.data.replace("neigh_", "")
    await state.update_data(neighborhood=neigh)
    data = await state.get_data()

    # ✅ Debug: اطبع البيانات بعد اختيار الحي
    print("📌 User registered data:", data)

    save_user(callback.from_user.id, data)

    if data.get("role") == "client":
        captains = find_captains(data["city"], data["neighborhood"])

        # ✅ Debug: اطبع شروط البحث والنتيجة
        print("🔍 Searching captains in:", data["city"], data["neighborhood"])
        print("🎯 Found captains:", captains)

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


@dp.callback_query(F.data.startswith("accept_"))
async def accept_handler(callback: types.CallbackQuery, state: FSMContext):
    captain_id = int(callback.data.split("_")[1])
    update_match(callback.from_user.id, captain_id, "pending")
    await bot.send_message(
        captain_id,
        f"📩 تم اختيارك من قبل عميل. اضغط ✅ للقبول أو ❌ للرفض.",
        reply_markup=captain_choice_keyboard(callback.from_user.id)
    )
    await callback.message.answer("✅ تم إرسال إشعار للكابتن، انتظر الرد...")
    
@dp.callback_query(F.data.startswith("reject_"))
async def reject_handler(callback: types.CallbackQuery, state: FSMContext):
    captain_id = int(callback.data.split("_")[1])
    update_match(callback.from_user.id, captain_id, "rejected")
    await callback.message.answer("❌ تم رفض الكابتن.")

@dp.callback_query(F.data.startswith("cap_accept_"))
async def captain_accept_handler(callback: types.CallbackQuery):
    client_id = int(callback.data.split("_")[2])  # فرضاً: cap_accept_{client_id}
    captain_id = callback.from_user.id
    
    # تحديث جدول matches
    update_match(client_id, captain_id, "accepted")
    
    # إشعار العميل
    await bot.send_message(client_id, f"✅ الكابتن وافق على التوصيل!")
    await callback.message.answer("✅ لقد وافقت على العميل.")

@dp.callback_query(F.data.startswith("cap_reject_"))
async def captain_reject_handler(callback: types.CallbackQuery):
    client_id = int(callback.data.split("_")[2])
    captain_id = callback.from_user.id
    
    update_match(client_id, captain_id, "rejected")
    
    await bot.send_message(client_id, f"❌ الكابتن رفض التوصيل.")
    await callback.message.answer("❌ لقد رفضت العميل.")

# ================== Main ==================
if __name__ == "__main__":
    init_db()
    asyncio.run(dp.start_polling(bot))



