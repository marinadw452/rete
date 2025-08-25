from aiogram import Router, types
from states import user_states
from keyboards import subscription_keyboard, city_keyboard, create_neighborhood_keyboard
from validators import valid_name, valid_phone
from database import get_conn

router = Router()

@router.callback_query(lambda c: c.data.startswith("role_captain"))
async def choose_role(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    state = user_states.get(user_id, {})
    
    state["role"] = "captain"
    state["step"] = "subscription"
    state["neighborhoods"] = []  # لتخزين ثلاثة أحياء
    user_states[user_id] = state
    
    await callback.message.answer("اختر نوع الاشتراك:", reply_markup=subscription_keyboard())

@router.callback_query(lambda c: c.data.startswith("sub_"))
async def choose_subscription(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    state = user_states.get(user_id)
    
    sub = callback.data.replace("sub_", "")
    state["subscription"] = sub
    state["step"] = "full_name"
    
    await callback.message.answer("اكتب اسمك الثلاثي:")

@router.message(lambda m: user_states.get(m.from_user.id, {}).get("step") == "full_name")
async def get_full_name(message: types.Message):
    user_id = message.from_user.id
    state = user_states[user_id]
    
    if not valid_name(message.text):
        return await message.reply("الرجاء إدخال الاسم الثلاثي بشكل صحيح.")
    
    state["full_name"] = message.text
    state["step"] = "phone"
    await message.answer("اكتب رقم جوالك (05XXXXXXXX):")

@router.message(lambda m: user_states.get(m.from_user.id, {}).get("step") == "phone")
async def get_phone(message: types.Message):
    user_id = message.from_user.id
    state = user_states[user_id]
    
    if not valid_phone(message.text):
        return await message.reply("رقم الجوال غير صحيح.")
    
    state["phone_number"] = message.text
    state["step"] = "car_type"
    await message.answer("اكتب نوع السيارة:")

@router.message(lambda m: user_states.get(m.from_user.id, {}).get("step") == "car_type")
async def get_car_type(message: types.Message):
    user_id = message.from_user.id
    state = user_states[user_id]
    
    state["car_type"] = message.text
    state["step"] = "plate_number"
    await message.answer("اكتب رقم لوحة السيارة:")

@router.message(lambda m: user_states.get(m.from_user.id, {}).get("step") == "plate_number")
async def get_plate_number(message: types.Message):
    user_id = message.from_user.id
    state = user_states[user_id]
    
    state["plate_number"] = message.text
    state["step"] = "capacity"
    await message.answer("اكتب عدد الركاب:")

@router.message(lambda m: user_states.get(m.from_user.id, {}).get("step") == "capacity")
async def get_capacity(message: types.Message):
    user_id = message.from_user.id
    state = user_states[user_id]
    
    try:
        cap = int(message.text)
        state["capacity"] = cap
    except ValueError:
        return await message.reply("الرجاء إدخال رقم صحيح للركاب.")
    
    state["step"] = "city"
    await message.answer("اختر مدينتك:", reply_markup=city_keyboard())

@router.callback_query(lambda c: c.data.startswith("city_"))
async def choose_city(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    state = user_states[user_id]
    
    city = callback.data.replace("city_", "")
    state["city"] = city
    state["step"] = "neighborhoods"
    state["neighborhoods"] = []
    
    await callback.message.answer(f"اختر أول حي من الثلاثة:", reply_markup=create_neighborhood_keyboard(city))

@router.callback_query(lambda c: c.data.startswith("neigh_"))
async def choose_neighborhood(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    state = user_states[user_id]
    
    neighborhood = callback.data.replace("neigh_", "")
    state["neighborhoods"].append(neighborhood)
    
    if len(state["neighborhoods"]) < 3:
        await callback.message.answer(f"اختر الحي رقم {len(state['neighborhoods']) + 1}:", reply_markup=create_neighborhood_keyboard(state["city"]))
    else:
        # حفظ الكابتن في DB
        conn = get_conn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE telegram_id=%s", (user_id,))
        existing = cursor.fetchone()
        
        neighborhoods_json = str(state["neighborhoods"])
        
        if existing:
            cursor.execute("""
                UPDATE users
                SET subscription=%s, full_name=%s, phone_number=%s, car_type=%s,
                    plate_number=%s, capacity=%s, city=%s, is_available=%s
                WHERE telegram_id=%s
            """, (state["subscription"], state["full_name"], state["phone_number"],
                  state["car_type"], state["plate_number"], state["capacity"],
                  state["city"], True, user_id))
        else:
            cursor.execute("""
                INSERT INTO users (telegram_id, role, subscription, full_name, phone_number,
                                   car_type, plate_number, capacity, city, is_available)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (user_id, "captain", state["subscription"], state["full_name"],
                  state["phone_number"], state["car_type"], state["plate_number"],
                  state["capacity"], state["city"], True))
        
        conn.commit()
        conn.close()
        
        state["step"] = "done"
        await callback.message.answer("تم حفظ بياناتك ✅\nانتظر المطابقة مع العملاء.")

def register_handlers(dp):
    dp.include_router(router)
