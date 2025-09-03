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

# ================== قاعدة البيانات ==================
def get_conn():
    """إنشاء اتصال بقاعدة البيانات"""
    return psycopg2.connect(
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        host=PG_HOST,
        port=PG_PORT,
        cursor_factory=psycopg2.extras.RealDictCursor
    )

def init_db():
    """إنشاء الجداول المطلوبة"""
    conn = get_conn()
    cur = conn.cursor()

    # جدول المستخدمين
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        username TEXT,
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
        is_available BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # جدول المطابقات/الطلبات
    cur.execute("""
    CREATE TABLE IF NOT EXISTS matches (
        id SERIAL PRIMARY KEY,
        client_id BIGINT REFERENCES users(user_id),
        captain_id BIGINT REFERENCES users(user_id),
        status VARCHAR(20) DEFAULT 'pending',
        client_confirmed BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT unique_pending_match UNIQUE (client_id, captain_id)
    )
    """)

    conn.commit()
    cur.close()
    conn.close()

def save_user(user_id, username, data):
    """حفظ بيانات المستخدم"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (user_id, username, role, subscription, full_name, phone, car_model, car_plate, seats, agreement, city, neighborhood, is_available)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE)
        ON CONFLICT (user_id) DO UPDATE SET
            username=EXCLUDED.username,
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
        user_id, username,
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

def find_available_captains(city, neighborhood):
    """البحث عن الكباتن المتاحين في المنطقة"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM users 
        WHERE role='captain' AND is_available=TRUE AND city=%s AND neighborhood=%s
        ORDER BY created_at ASC
    """, (city, neighborhood))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_user_by_id(user_id):
    """جلب بيانات المستخدم"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user

def create_match_request(client_id, captain_id):
    """إنشاء طلب جديد"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO matches (client_id, captain_id, status)
            VALUES (%s, %s, 'pending')
        """, (client_id, captain_id))
        conn.commit()
        return True
    except psycopg2.IntegrityError:
        # الطلب موجود مسبقاً
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

def update_match_status(client_id, captain_id, status, client_confirmed=None):
    """تحديث حالة الطلب"""
    conn = get_conn()
    cur = conn.cursor()
    
    if client_confirmed is not None:
        cur.execute("""
            UPDATE matches 
            SET status=%s, client_confirmed=%s, updated_at=CURRENT_TIMESTAMP
            WHERE client_id=%s AND captain_id=%s
        """, (status, client_confirmed, client_id, captain_id))
    else:
        cur.execute("""
            UPDATE matches 
            SET status=%s, updated_at=CURRENT_TIMESTAMP
            WHERE client_id=%s AND captain_id=%s
        """, (status, client_id, captain_id))

    # تحديث توفر الكابتن
    if status == "captain_accepted":
        # الكابتن قبل، لكن لا نغير التوفر حتى يوافق العميل
        pass
    elif status == "completed":
        # العميل وافق، الكابتن أصبح غير متاح
        cur.execute("UPDATE users SET is_available=FALSE WHERE user_id=%s", (captain_id,))
    elif status in ["rejected", "cancelled"]:
        # إعادة الكابتن للتوفر
        cur.execute("UPDATE users SET is_available=TRUE WHERE user_id=%s", (captain_id,))

    conn.commit()
    cur.close()
    conn.close()

def reset_captain_availability(captain_id):
    """إعادة الكابتن للحالة المتاحة"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_available=TRUE WHERE user_id=%s", (captain_id,))
    conn.commit()
    cur.close()
    conn.close()

def is_user_registered(user_id):
    """التحقق من تسجيل المستخدم"""
    user = get_user_by_id(user_id)
    return user is not None

def update_user_field(user_id, field, value):
    """تحديث حقل واحد في بيانات المستخدم"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE users SET {field}=%s WHERE user_id=%s", (value, user_id))
    conn.commit()
    cur.close()
    conn.close()

def get_user_stats(user_id):
    """جلب إحصائيات المستخدم"""
    conn = get_conn()
    cur = conn.cursor()
    
    user = get_user_by_id(user_id)
    if not user:
        return None
    
    if user['role'] == 'client':
        cur.execute("""
            SELECT 
                COUNT(*) as total_requests,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_trips,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_requests
            FROM matches WHERE client_id = %s
        """, (user_id,))
    else:
        cur.execute("""
            SELECT 
                COUNT(*) as total_requests,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_trips,
                COUNT(CASE WHEN status = 'captain_accepted' THEN 1 END) as accepted_requests
            FROM matches WHERE captain_id = %s
        """, (user_id,))
    
    stats = cur.fetchone()
    cur.close()
    conn.close()
    return stats

# ================== حالات التسجيل ==================
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

class EditStates(StatesGroup):
    edit_name = State()
    edit_phone = State()
    edit_car_model = State()
    edit_car_plate = State()
    edit_seats = State()
    change_city = State()
    change_neighborhood = State()
    select_destination = State()

# ================== أزرار التحكم ==================
def start_keyboard():
    """أزرار اختيار الدور"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🚕 عميل", callback_data="role_client")
    builder.button(text="🧑‍✈️ كابتن", callback_data="role_captain")
    builder.adjust(2)
    return builder.as_markup()

def subscription_keyboard():
    """أزرار نوع الاشتراك"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 يومي", callback_data="sub_daily")
    builder.button(text="📆 شهري", callback_data="sub_monthly")
    builder.adjust(2)
    return builder.as_markup()

def agreement_keyboard():
    """زر الموافقة على الشروط"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ أوافق على الشروط والأحكام", callback_data="agree")
    return builder.as_markup()

def city_keyboard():
    """أزرار اختيار المدينة"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🏙️ الرياض", callback_data="city_الرياض")
    builder.button(text="🌆 جدة", callback_data="city_جدة")
    builder.adjust(1)
    return builder.as_markup()

def neighborhood_keyboard(city):
    """أزرار اختيار الحي"""
    try:
        with open("neighborhoods.json", "r", encoding="utf-8") as f:
            neighborhoods_data = json.load(f)
            
        builder = InlineKeyboardBuilder()
        for neighborhood in neighborhoods_data.get(city, []):
            builder.button(text=neighborhood, callback_data=f"neigh_{neighborhood}")
        builder.adjust(2)
        return builder.as_markup()
        
    except FileNotFoundError:
        # إذا الملف مو موجود
        builder = InlineKeyboardBuilder()
        builder.button(text="❌ ملف الأحياء غير موجود", callback_data="error_no_file")
        return builder.as_markup()

def captain_selection_keyboard(captain_id):
    """زر اختيار الكابتن"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🚖 اختيار هذا الكابتن", callback_data=f"choose_{captain_id}")
    return builder.as_markup()

def captain_response_keyboard(client_id):
    """أزرار رد الكابتن"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ قبول الطلب", callback_data=f"captain_accept_{client_id}")
    builder.button(text="❌ رفض الطلب", callback_data=f"captain_reject_{client_id}")
    builder.adjust(2)
    return builder.as_markup()

def client_confirmation_keyboard(captain_id):
    """أزرار موافقة العميل النهائية"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ موافق، ابدأ الرحلة", callback_data=f"client_confirm_{captain_id}")
    builder.button(text="❌ إلغاء الطلب", callback_data=f"client_cancel_{captain_id}")
    builder.adjust(2)
    return builder.as_markup()

def contact_captain_keyboard(captain_username):
    """زر التواصل مع الكابتن"""
    builder = InlineKeyboardBuilder()
    if captain_username:
        builder.button(text="💬 تواصل مع الكابتن", url=f"https://t.me/{captain_username}")
    return builder.as_markup()

def main_menu_keyboard(role):
    """القائمة الرئيسية للمستخدم المسجل"""
    builder = InlineKeyboardBuilder()
    
    if role == "client":
        builder.button(text="🚕 طلب توصيلة", callback_data="request_ride")
        builder.button(text="🏘️ تغيير الوجهة", callback_data="change_destination")
    else:  # captain
        builder.button(text="🟢 متاح للتوصيل", callback_data="set_available")
        builder.button(text="🔴 غير متاح", callback_data="set_unavailable")
        builder.button(text="📍 تغيير المنطقة", callback_data="change_location")
    
    builder.button(text="⚙️ تعديل البيانات", callback_data="edit_profile")
    builder.button(text="📊 إحصائياتي", callback_data="my_stats")
    builder.adjust(2, 1)
    return builder.as_markup()

def edit_profile_keyboard(role):
    """أزرار تعديل البيانات"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="👤 تعديل الاسم", callback_data="edit_name")
    builder.button(text="📱 تعديل الجوال", callback_data="edit_phone")
    
    if role == "captain":
        builder.button(text="🚘 تعديل السيارة", callback_data="edit_car")
        builder.button(text="🚪 تعديل المقاعد", callback_data="edit_seats")
    
    builder.button(text="🌆 تغيير المدينة", callback_data="edit_city")
    builder.button(text="🏘️ تغيير الحي", callback_data="edit_neighborhood")
    builder.button(text="🔙 العودة للقائمة", callback_data="back_to_main")
    builder.adjust(2)
    return builder.as_markup()

def destination_keyboard(city):
    """أزرار اختيار الوجهة للعميل"""
    try:
        with open("neighborhoods.json", "r", encoding="utf-8") as f:
            neighborhoods_data = json.load(f)
            
        builder = InlineKeyboardBuilder()
        builder.button(text="📍 نفس المنطقة", callback_data="dest_same")
        
        for neighborhood in neighborhoods_data.get(city, []):
            builder.button(text=neighborhood, callback_data=f"dest_{neighborhood}")
        
        builder.button(text="🔙 رجوع", callback_data="back_to_main")
        builder.adjust(2)
        return builder.as_markup()
        
    except FileNotFoundError:
        builder = InlineKeyboardBuilder()
        builder.button(text="❌ ملف الأحياء غير موجود", callback_data="error_no_file")
        return builder.as_markup()

# ================== إعداد البوت ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================== معالجات الأحداث ==================

@dp.message(F.text == "/start")
async def start_command(message: types.Message, state: FSMContext):
    """بداية التسجيل أو القائمة الرئيسية"""
    await state.clear()
    user_id = message.from_user.id
    
    # التحقق من تسجيل المستخدم
    if is_user_registered(user_id):
        user = get_user_by_id(user_id)
        role_text = "العميل" if user['role'] == 'client' else "الكابتن"
        
        welcome_back = f"""
🎉 أهلاً وسهلاً {user['full_name']}!

أنت مسجل كـ {role_text} في منطقة:
📍 {user['city']} - {user['neighborhood']}

اختر العملية المطلوبة:
        """
        
        await message.answer(welcome_back, reply_markup=main_menu_keyboard(user['role']))
    else:
        # مستخدم جديد - عرض شاشة التسجيل
        welcome_text = """
🌟 مرحباً بك في نظام طقطق للمواصلات 🌟

اختر دورك في النظام:
🚕 العميل: يطلب توصيلة
🧑‍✈️ الكابتن: يقدم خدمة التوصيل
        """
        await message.answer(welcome_text, reply_markup=start_keyboard())
        await state.set_state(RegisterStates.role)

# ================== معالجات التسجيل ==================

@dp.callback_query(F.data.startswith("role_"))
async def handle_role_selection(callback: types.CallbackQuery, state: FSMContext):
    """معالج اختيار الدور"""
    role = callback.data.split("_")[1]
    await state.update_data(role=role)
    
    role_text = "عميل" if role == "client" else "كابتن"
    await callback.message.edit_text(
        f"✅ اخترت دور: {role_text}\n\nاختر نوع الاشتراك:",
        reply_markup=subscription_keyboard()
    )
    await state.set_state(RegisterStates.subscription)

@dp.callback_query(F.data.startswith("sub_"))
async def handle_subscription(callback: types.CallbackQuery, state: FSMContext):
    """معالج نوع الاشتراك"""
    subscription = callback.data.split("_")[1]
    await state.update_data(subscription=subscription)
    
    sub_text = "يومي" if subscription == "daily" else "شهري"
    await callback.message.edit_text(f"✅ نوع الاشتراك: {sub_text}")
    await callback.message.answer("👤 أدخل اسمك الكامل:")
    await state.set_state(RegisterStates.full_name)

@dp.message(RegisterStates.full_name)
async def handle_full_name(message: types.Message, state: FSMContext):
    """معالج الاسم الكامل"""
    await state.update_data(full_name=message.text)
    await message.answer("📱 أدخل رقم جوالك:")
    await state.set_state(RegisterStates.phone)

@dp.message(RegisterStates.phone)
async def handle_phone(message: types.Message, state: FSMContext):
    """معالج رقم الجوال"""
    await state.update_data(phone=message.text)
    data = await state.get_data()
    
    if data.get("role") == "captain":
        await message.answer("🚘 أدخل موديل السيارة (مثال: كامري 2020):")
        await state.set_state(RegisterStates.car_model)
    else:
        await message.answer(
            "📋 الشروط والأحكام:\n"
            "• الالتزام بأنظمة المرور والسلامة\n"
            "• احترام الآخرين والتعامل بأدب\n"
            "• عدم إلحاق الضرر بالممتلكات\n"
            "• الالتزام بالمواعيد المحددة\n\n"
            "اضغط للموافقة والمتابعة:",
            reply_markup=agreement_keyboard()
        )
        await state.set_state(RegisterStates.agreement)

@dp.message(RegisterStates.car_model)
async def handle_car_model(message: types.Message, state: FSMContext):
    """معالج موديل السيارة"""
    await state.update_data(car_model=message.text)
    await message.answer("🔢 أدخل رقم اللوحة (مثال: أ ب ج 1234):")
    await state.set_state(RegisterStates.car_plate)

@dp.message(RegisterStates.car_plate)
async def handle_car_plate(message: types.Message, state: FSMContext):
    """معالج رقم اللوحة"""
    await state.update_data(car_plate=message.text)
    await message.answer("🚪 كم عدد المقاعد المتاحة للركاب؟")
    await state.set_state(RegisterStates.seats)

@dp.message(RegisterStates.seats)
async def handle_seats(message: types.Message, state: FSMContext):
    """معالج عدد المقاعد"""
    try:
        seats = int(message.text)
        if seats < 1 or seats > 8:
            await message.answer("❌ عدد المقاعد يجب أن يكون بين 1 و 8")
            return
        await state.update_data(seats=seats)
        await message.answer(
            "📋 الشروط والأحكام للكباتن:\n"
            "• وجود رخصة قيادة سارية\n"
            "• تأمين ساري للمركبة\n"
            "• الالتزام بأنظمة المرور\n"
            "• التعامل باحترام مع العملاء\n"
            "• المحافظة على نظافة المركبة\n\n"
            "اضغط للموافقة والمتابعة:",
            reply_markup=agreement_keyboard()
        )
        await state.set_state(RegisterStates.agreement)
    except ValueError:
        await message.answer("❌ يرجى إدخال رقم صحيح")

@dp.callback_query(F.data == "agree")
async def handle_agreement(callback: types.CallbackQuery, state: FSMContext):
    """معالج الموافقة على الشروط"""
    await state.update_data(agreement=True)
    await callback.message.edit_text(
        "✅ تمت الموافقة على الشروط\n\n🌆 اختر مدينتك:",
        reply_markup=city_keyboard()
    )
    await state.set_state(RegisterStates.city)

@dp.callback_query(F.data.startswith("city_"))
async def handle_city_selection(callback: types.CallbackQuery, state: FSMContext):
    """معالج اختيار المدينة"""
    city = callback.data.split("_")[1]
    await state.update_data(city=city)
    await callback.message.edit_text(
        f"✅ المدينة: {city}\n\n🏘️ اختر الحي:",
        reply_markup=neighborhood_keyboard(city)
    )
    await state.set_state(RegisterStates.neighborhood)

@dp.callback_query(F.data.startswith("neigh_"), RegisterStates.neighborhood)
async def handle_neighborhood_selection(callback: types.CallbackQuery, state: FSMContext):
    """معالج اختيار الحي وإنهاء التسجيل"""
    neighborhood = callback.data.replace("neigh_", "")
    await state.update_data(neighborhood=neighborhood)
    data = await state.get_data()

    # حفظ بيانات المستخدم
    username = callback.from_user.username
    save_user(callback.from_user.id, username, data)

    if data.get("role") == "client":
        # العميل - البحث عن كباتن
        await callback.message.edit_text(f"✅ تم التسجيل بنجاح في {neighborhood}")
        await search_for_captains(callback.message, data["city"], data["neighborhood"])
    else:
        # الكابتن - انتظار الطلبات
        await callback.message.edit_text(
            f"✅ تم تسجيلك ككابتن بنجاح!\n\n"
            f"📍 المنطقة: {data['city']} - {neighborhood}\n"
            f"🚘 المركبة: {data['car_model']} ({data['car_plate']})\n"
            f"🚪 المقاعد: {data['seats']}\n\n"
            f"سيتم إشعارك عند وصول طلبات جديدة..."
        )

    await state.clear()

# ================== معالجات القائمة الرئيسية ==================

@dp.callback_query(F.data == "request_ride")
async def request_ride_handler(callback: types.CallbackQuery, state: FSMContext):
    """طلب توصيلة جديدة"""
    user = get_user_by_id(callback.from_user.id)
    if not user:
        await callback.answer("❌ خطأ في البيانات", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"📍 موقعك الحالي: {user['city']} - {user['neighborhood']}\n\n"
        f"🎯 اختر الوجهة التي تريد الذهاب إليها:",
        reply_markup=destination_keyboard(user['city'])
    )
    await state.set_state(EditStates.select_destination)

@dp.callback_query(F.data.startswith("dest_"))
async def handle_destination_selection(callback: types.CallbackQuery, state: FSMContext):
    """معالج اختيار الوجهة"""
    destination = callback.data.replace("dest_", "")
    user = get_user_by_id(callback.from_user.id)
    
    if destination == "same":
        # نفس المنطقة
        search_neighborhood = user['neighborhood']
        destination_text = f"{user['city']} - {user['neighborhood']}"
    else:
        # منطقة مختلفة
        search_neighborhood = destination
        destination_text = f"{user['city']} - {destination}"
    
    await callback.message.edit_text(
        f"🎯 الوجهة المختارة: {destination_text}\n\n"
        f"🔍 جاري البحث عن الكباتن المتاحين..."
    )
    
    await search_for_captains(callback.message, user['city'], search_neighborhood)
    await state.clear()

@dp.callback_query(F.data == "change_destination")
async def change_destination_handler(callback: types.CallbackQuery, state: FSMContext):
    """تغيير الوجهة"""
    await request_ride_handler(callback, state)

@dp.callback_query(F.data == "set_available")
async def set_captain_available(callback: types.CallbackQuery):
    """تعيين الكابتن كمتاح"""
    user_id = callback.from_user.id
    update_user_field(user_id, "is_available", True)
    
    await callback.message.edit_text(
        "🟢 تم تعيينك كمتاح للتوصيل!\n\n"
        "سيتم إشعارك عند وصول طلبات جديدة...",
        reply_markup=main_menu_keyboard("captain")
    )

@dp.callback_query(F.data == "set_unavailable")
async def set_captain_unavailable(callback: types.CallbackQuery):
    """تعيين الكابتن كغير متاح"""
    user_id = callback.from_user.id
    update_user_field(user_id, "is_available", False)
    
    await callback.message.edit_text(
        "🔴 تم تعيينك كغير متاح للتوصيل\n\n"
        "لن تصلك طلبات جديدة حتى تقوم بتفعيل الحالة مرة أخرى",
        reply_markup=main_menu_keyboard("captain")
    )

@dp.callback_query(F.data == "change_location")
async def change_captain_location(callback: types.CallbackQuery, state: FSMContext):
    """تغيير منطقة الكابتن"""
    await callback.message.edit_text(
        "📍 تغيير المنطقة\n\n🌆 اختر المدينة الجديدة:",
        reply_markup=city_keyboard()
    )
    await state.set_state(EditStates.change_city)

@dp.callback_query(F.data == "edit_profile")
async def edit_profile_handler(callback: types.CallbackQuery):
    """تعديل البيانات الشخصية"""
    user = get_user_by_id(callback.from_user.id)
    if not user:
        await callback.answer("❌ خطأ في البيانات", show_alert=True)
        return
    
    profile_info = f"""
👤 بياناتك الحالية:

📛 الاسم: {user['full_name']}
📱 الجوال: {user['phone']}
📍 المنطقة: {user['city']} - {user['neighborhood']}
    """
    
    if user['role'] == 'captain':
        profile_info += f"""
🚘 السيارة: {user['car_model']}
🔢 اللوحة: {user['car_plate']}
🚪 المقاعد: {user['seats']}
        """
    
    profile_info += "\n\nاختر البيان الذي تريد تعديله:"
    
    await callback.message.edit_text(
        profile_info,
        reply_markup=edit_profile_keyboard(user['role'])
    )

@dp.callback_query(F.data == "my_stats")
async def show_user_stats(callback: types.CallbackQuery):
    """عرض إحصائيات المستخدم"""
    user = get_user_by_id(callback.from_user.id)
    stats = get_user_stats(callback.from_user.id)
    
    if not user or not stats:
        await callback.answer("❌ لا توجد إحصائيات", show_alert=True)
        return
    
    if user['role'] == 'client':
        stats_text = f"""
📊 إحصائياتك كعميل:

🔢 إجمالي الطلبات: {stats['total_requests']}
✅ الرحلات المكتملة: {stats['completed_trips']}
⏳ الطلبات المعلقة: {stats['pending_requests']}
        """
    else:
        stats_text = f"""
📊 إحصائياتك ككابتن:

🔢 إجمالي الطلبات: {stats['total_requests']}
✅ الرحلات المكتملة: {stats['completed_trips']}
👍 الطلبات المقبولة: {stats['accepted_requests']}
🔄 حالتك: {"متاح" if user['is_available'] else "غير متاح"}
        """
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 العودة للقائمة", callback_data="back_to_main")
    
    await callback.message.edit_text(stats_text, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: types.CallbackQuery, state: FSMContext):
    """العودة للقائمة الرئيسية"""
    await state.clear()
    user = get_user_by_id(callback.from_user.id)
    
    role_text = "العميل" if user['role'] == 'client' else "الكابتن"
    status_text = ""
    
    if user['role'] == 'captain':
        status_text = f"\n🟢 الحالة: {'متاح' if user['is_available'] else 'غير متاح'}"
    
    main_menu_text = f"""
🏠 القائمة الرئيسية

👤 {user['full_name']} ({role_text})
📍 {user['city']} - {user['neighborhood']}{status_text}

اختر العملية المطلوبة:
    """
    
    await callback.message.edit_text(
        main_menu_text,
        reply_markup=main_menu_keyboard(user['role'])
    )

# ================== معالجات تعديل البيانات ==================

@dp.callback_query(F.data == "edit_name")
async def edit_name_handler(callback: types.CallbackQuery, state: FSMContext):
    """تعديل الاسم"""
    await callback.message.edit_text("👤 أدخل الاسم الجديد:")
    await state.set_state(EditStates.edit_name)

@dp.message(EditStates.edit_name)
async def handle_new_name(message: types.Message, state: FSMContext):
    """معالج الاسم الجديد"""
    update_user_field(message.from_user.id, "full_name", message.text)
    await message.answer("✅ تم تحديث الاسم بنجاح!")
    
    # العودة لقائمة التعديل
    user = get_user_by_id(message.from_user.id)
    await message.answer(
        "⚙️ تعديل البيانات\n\nاختر البيان الذي تريد تعديله:",
        reply_markup=edit_profile_keyboard(user['role'])
    )
    await state.clear()

@dp.callback_query(F.data == "edit_phone")
async def edit_phone_handler(callback: types.CallbackQuery, state: FSMContext):
    """تعديل الجوال"""
    await callback.message.edit_text("📱 أدخل رقم الجوال الجديد:")
    await state.set_state(EditStates.edit_phone)

@dp.message(EditStates.edit_phone)
async def handle_new_phone(message: types.Message, state: FSMContext):
    """معالج رقم الجوال الجديد"""
    update_user_field(message.from_user.id, "phone", message.text)
    await message.answer("✅ تم تحديث رقم الجوال بنجاح!")
    
    user = get_user_by_id(message.from_user.id)
    await message.answer(
        "⚙️ تعديل البيانات\n\nاختر البيان الذي تريد تعديله:",
        reply_markup=edit_profile_keyboard(user['role'])
    )
    await state.clear()

@dp.callback_query(F.data == "edit_car")
async def edit_car_handler(callback: types.CallbackQuery, state: FSMContext):
    """تعديل بيانات السيارة"""
    await callback.message.edit_text("🚘 أدخل موديل السيارة الجديد:")
    await state.set_state(EditStates.edit_car_model)

@dp.message(EditStates.edit_car_model)
async def handle_new_car_model(message: types.Message, state: FSMContext):
    """معالج موديل السيارة الجديد"""
    await state.update_data(new_car_model=message.text)
    await message.answer("🔢 أدخل رقم اللوحة الجديد:")
    await state.set_state(EditStates.edit_car_plate)

@dp.message(EditStates.edit_car_plate)
async def handle_new_car_plate(message: types.Message, state: FSMContext):
    """معالج رقم اللوحة الجديد"""
    data = await state.get_data()
    
    # تحديث بيانات السيارة
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users SET car_model=%s, car_plate=%s 
        WHERE user_id=%s
    """, (data['new_car_model'], message.text, message.from_user.id))
    conn.commit()
    cur.close()
    conn.close()
    
    await message.answer("✅ تم تحديث بيانات السيارة بنجاح!")
    
    user = get_user_by_id(message.from_user.id)
    await message.answer(
        "⚙️ تعديل البيانات\n\nاختر البيان الذي تريد تعديله:",
        reply_markup=edit_profile_keyboard(user['role'])
    )
    await state.clear()

@dp.callback_query(F.data == "edit_seats")
async def edit_seats_handler(callback: types.CallbackQuery, state: FSMContext):
    """تعديل عدد المقاعد"""
    await callback.message.edit_text("🚪 أدخل عدد المقاعد الجديد:")
    await state.set_state(EditStates.edit_seats)

@dp.message(EditStates.edit_seats)
async def handle_new_seats(message: types.Message, state: FSMContext):
    """معالج عدد المقاعد الجديد"""
    try:
        seats = int(message.text)
        if seats < 1 or seats > 8:
            await message.answer("❌ عدد المقاعد يجب أن يكون بين 1 و 8")
            return
            
        update_user_field(message.from_user.id, "seats", seats)
        await message.answer("✅ تم تحديث عدد المقاعد بنجاح!")
        
        user = get_user_by_id(message.from_user.id)
        await message.answer(
            "⚙️ تعديل البيانات\n\nاختر البيان الذي تريد تعديله:",
            reply_markup=edit_profile_keyboard(user['role'])
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ يرجى إدخال رقم صحيح")

@dp.callback_query(F.data == "edit_city")
async def edit_city_handler(callback: types.CallbackQuery, state: FSMContext):
    """تعديل المدينة"""
    await callback.message.edit_text(
        "🌆 اختر المدينة الجديدة:",
        reply_markup=city_keyboard()
    )
    await state.set_state(EditStates.change_city)

# معالجات تغيير المدينة والحي (مشتركة)
@dp.callback_query(F.data.startswith("city_"), EditStates.change_city)
async def handle_city_change(callback: types.CallbackQuery, state: FSMContext):
    """معالج تغيير المدينة"""
    city = callback.data.split("_")[1]
    await state.update_data(new_city=city)
    await callback.message.edit_text(
        f"✅ المدينة الجديدة: {city}\n\n🏘️ اختر الحي الجديد:",
        reply_markup=neighborhood_keyboard(city)
    )
    await state.set_state(EditStates.change_neighborhood)

@dp.callback_query(F.data.startswith("neigh_"), EditStates.change_neighborhood)
async def handle_neighborhood_change(callback: types.CallbackQuery, state: FSMContext):
    """معالج تغيير الحي"""
    neighborhood = callback.data.replace("neigh_", "")
    data = await state.get_data()
    new_city = data.get('new_city')
    
    # تحديث المدينة والحي
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users SET city=%s, neighborhood=%s 
        WHERE user_id=%s
    """, (new_city, neighborhood, callback.from_user.id))
    conn.commit()
    cur.close()
    conn.close()
    
    await callback.message.edit_text(
        f"✅ تم تحديث المنطقة بنجاح!\n\n"
        f"📍 المنطقة الجديدة: {new_city} - {neighborhood}"
    )
    
    # العودة للقائمة الرئيسية
    user = get_user_by_id(callback.from_user.id)
    await asyncio.sleep(2)  # انتظار قصير
    await callback.message.edit_text(
        f"🏠 القائمة الرئيسية\n\n"
        f"👤 {user['full_name']}\n"
        f"📍 {new_city} - {neighborhood}",
        reply_markup=main_menu_keyboard(user['role'])
    )
    await state.clear()

# ================== معالجات البحث والطلبات ==================

async def search_for_captains(message, city, neighborhood):
    """البحث عن الكباتن وعرضهم للعميل"""
    captains = find_available_captains(city, neighborhood)
    
    if not captains:
        await message.answer(
            "😔 عذراً، لا يوجد كباتن متاحين في منطقتك حالياً.\n\n"
            "💡 نصائح:\n"
            "• جرب مرة أخرى بعد قليل\n"
            "• تأكد من اختيار الحي الصحيح\n"
            "• يمكنك إعادة المحاولة بإرسال /start"
        )
        return

    await message.answer(f"🎉 وُجد {len(captains)} كابتن متاح في منطقتك!")
    
    for captain in captains:
        captain_info = (
            f"👨‍✈️ الكابتن: {captain['full_name']}\n"
            f"🚘 السيارة: {captain['car_model']}\n"
            f"🔢 اللوحة: {captain['car_plate']}\n"
            f"🚪 المقاعد المتاحة: {captain['seats']}\n"
            f"📍 المنطقة: {captain['city']} - {captain['neighborhood']}"
        )
        
        await message.answer(
            captain_info,
            reply_markup=captain_selection_keyboard(captain["user_id"])
        )

@dp.callback_query(F.data.startswith("choose_"))
async def handle_captain_selection(callback: types.CallbackQuery):
    """معالج اختيار العميل للكابتن"""
    captain_id = int(callback.data.split("_")[1])
    client_id = callback.from_user.id

    # إنشاء طلب جديد
    if not create_match_request(client_id, captain_id):
        await callback.answer("⚠️ لديك طلب مُعلق مع هذا الكابتن", show_alert=True)
        return

    # جلب بيانات العميل
    client = get_user_by_id(client_id)
    captain = get_user_by_id(captain_id)

    if not client or not captain:
        await callback.answer("❌ خطأ في البيانات", show_alert=True)
        return

    # إشعار الكابتن
    notification_text = (
        f"🚖 طلب رحلة جديد!\n\n"
        f"👤 العميل: {client['full_name']}\n"
        f"📱 الجوال: {client['phone']}\n"
        f"📍 المنطقة: {client['city']} - {client['neighborhood']}\n\n"
        f"هل تقبل هذا الطلب؟"
    )

    await bot.send_message(
        captain_id,
        notification_text,
        reply_markup=captain_response_keyboard(client_id)
    )

    await callback.message.edit_text("⏳ تم إرسال طلبك للكابتن، يرجى انتظار الرد...")

@dp.callback_query(F.data.startswith("captain_accept_"))
async def handle_captain_acceptance(callback: types.CallbackQuery):
    """معالج قبول الكابتن للطلب"""
    client_id = int(callback.data.split("_")[2])
    captain_id = callback.from_user.id

    # تحديث حالة الطلب
    update_match_status(client_id, captain_id, "captain_accepted")

    # جلب بيانات الكابتن
    captain = get_user_by_id(captain_id)

    await callback.message.edit_text(
        f"✅ تم قبول الطلب!\n\n"
        f"ننتظر موافقة العميل النهائية..."
    )

    # إشعار العميل بقبول الكابتن
    client_notification = (
        f"🎉 الكابتن قبل طلبك!\n\n"
        f"👨‍✈️ الكابتن: {captain['full_name']}\n"
        f"🚘 السيارة: {captain['car_model']} ({captain['car_plate']})\n"
        f"🚪 المقاعد: {captain['seats']}\n"
        f"📱 الجوال: {captain['phone']}\n\n"
        f"هل توافق على بدء الرحلة؟"
    )

    await bot.send_message(
        client_id,
        client_notification,
        reply_markup=client_confirmation_keyboard(captain_id)
    )

@dp.callback_query(F.data.startswith("captain_reject_"))
async def handle_captain_rejection(callback: types.CallbackQuery):
    """معالج رفض الكابتن للطلب"""
    client_id = int(callback.data.split("_")[2])
    captain_id = callback.from_user.id

    # تحديث حالة الطلب
    update_match_status(client_id, captain_id, "rejected")

    await callback.message.edit_text("❌ تم رفض الطلب")

    # إشعار العميل بالرفض
    client = get_user_by_id(client_id)
    await bot.send_message(
        client_id,
        f"😔 عذراً، الكابتن غير متاح حالياً\n\n"
        f"يمكنك اختيار كابتن آخر أو المحاولة لاحقاً\n"
        f"إرسال /start للبحث مرة أخرى"
    )

    # البحث عن كباتن آخرين
    if client:
        await search_for_captains(
            await bot.send_message(client_id, "🔍 البحث عن كباتن آخرين..."),
            client['city'],
            client['neighborhood']
        )

@dp.callback_query(F.data.startswith("client_confirm_"))
async def handle_client_confirmation(callback: types.CallbackQuery):
    """معالج موافقة العميل النهائية"""
    captain_id = int(callback.data.split("_")[2])
    client_id = callback.from_user.id

    # تحديث حالة الطلب إلى مكتمل
    update_match_status(client_id, captain_id, "completed", client_confirmed=True)

    # جلب بيانات الكابتن والعميل
    captain = get_user_by_id(captain_id)
    client = get_user_by_id(client_id)

    # إشعار العميل
    success_message = (
        f"✅ تم تأكيد الرحلة بنجاح!\n\n"
        f"👨‍✈️ الكابتن: {captain['full_name']}\n"
        f"📱 جوال الكابتن: {captain['phone']}\n"
        f"🚘 السيارة: {captain['car_model']} ({captain['car_plate']})\n\n"
        f"🎯 تواصل مع الكابتن لتحديد نقطة الالتقاء\n"
        f"🙏 نتمنى لك رحلة سعيدة!"
    )

    keyboard = contact_captain_keyboard(captain.get('username'))
    await callback.message.edit_text(success_message, reply_markup=keyboard)

    # إشعار الكابتن
    captain_notification = (
        f"🎉 تم تأكيد الرحلة!\n\n"
        f"👤 العميل: {client['full_name']}\n"
        f"📱 جوال العميل: {client['phone']}\n"
        f"📍 المنطقة: {client['city']} - {client['neighborhood']}\n\n"
        f"📞 تواصل مع العميل لتحديد التفاصيل"
    )

    client_contact_keyboard = InlineKeyboardBuilder()
    if client.get('username'):
        client_contact_keyboard.button(
            text="💬 تواصل مع العميل",
            url=f"https://t.me/{client['username']}"
        )

    await bot.send_message(
        captain_id,
        captain_notification,
        reply_markup=client_contact_keyboard.as_markup()
    )

@dp.callback_query(F.data.startswith("client_cancel_"))
async def handle_client_cancellation(callback: types.CallbackQuery):
    """معالج إلغاء العميل للطلب"""
    captain_id = int(callback.data.split("_")[2])
    client_id = callback.from_user.id

    # تحديث حالة الطلب وإعادة الكابتن للتوفر
    update_match_status(client_id, captain_id, "cancelled")
    reset_captain_availability(captain_id)

    await callback.message.edit_text(
        f"❌ تم إلغاء الطلب\n\n"
        f"يمكنك البحث عن كابتن آخر بإرسال /start"
    )

    # إشعار الكابتن بالإلغاء
    await bot.send_message(
        captain_id,
        f"ℹ️ تم إلغاء الطلب من قبل العميل\n"
        f"يمكنك استقبال طلبات أخرى الآن"
    )

# ================== تشغيل البوت ==================
if __name__ == "__main__":
    print("🚀 بدء تشغيل بوت طقطق...")
    try:
        init_db()
        print("✅ تم الاتصال بقاعدة البيانات")
        asyncio.run(dp.start_polling(bot))
    except Exception as e:
        print(f"❌ خطأ في التشغيل: {e}")
