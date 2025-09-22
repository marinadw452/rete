import asyncio
import json
import psycopg2
import psycopg2.extras
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
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
        agreement BOOLEAN DEFAULT FALSE,
        city TEXT,
        neighborhood TEXT,
        neighborhood2 TEXT,
        neighborhood3 TEXT,
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
        destination TEXT,
        status VARCHAR(20) DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT unique_pending_match UNIQUE (client_id, captain_id)
    )
    """)

    # جدول التقييمات مع حقل الملاحظات
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ratings (
        id SERIAL PRIMARY KEY,
        match_id INTEGER REFERENCES matches(id),
        client_id BIGINT REFERENCES users(user_id),
        captain_id BIGINT REFERENCES users(user_id),
        rating INTEGER CHECK (rating >= 1 AND rating <= 5),
        comment TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT unique_rating UNIQUE (match_id, client_id)
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
        INSERT INTO users (user_id, username, role, subscription, full_name, phone, car_model, car_plate, agreement, city, neighborhood, neighborhood2, neighborhood3, is_available)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE)
        ON CONFLICT (user_id) DO UPDATE SET
            username=EXCLUDED.username,
            role=EXCLUDED.role,
            subscription=EXCLUDED.subscription,
            full_name=EXCLUDED.full_name,
            phone=EXCLUDED.phone,
            car_model=EXCLUDED.car_model,
            car_plate=EXCLUDED.car_plate,
            agreement=EXCLUDED.agreement,
            city=EXCLUDED.city,
            neighborhood=EXCLUDED.neighborhood,
            neighborhood2=EXCLUDED.neighborhood2,
            neighborhood3=EXCLUDED.neighborhood3,
            is_available=TRUE
    """, (
        user_id, username,
        data.get("role"),
        data.get("subscription"),
        data.get("full_name"),
        data.get("phone"),
        data.get("car_model"),
        data.get("car_plate"),
        data.get("agreement"),
        data.get("city"),
        data.get("neighborhood"),
        data.get("neighborhood2"),
        data.get("neighborhood3"),
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
        WHERE role='captain' AND is_available=TRUE AND city=%s 
        AND (%s = neighborhood OR %s = neighborhood2 OR %s = neighborhood3)
        ORDER BY created_at ASC
    """, (city, neighborhood, neighborhood, neighborhood))
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

def create_match_request(client_id, captain_id, destination):
    """إنشاء طلب جديد مع حفظ الوجهة بشكل صحيح"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO matches (client_id, captain_id, destination, status)
            VALUES (%s, %s, %s, 'pending')
            RETURNING id
        """, (client_id, captain_id, destination))
        match_id = cur.fetchone()['id']
        conn.commit()
        return match_id
    except psycopg2.IntegrityError:
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()

def update_match_status(client_id, captain_id, status):
    """تحديث حالة الطلب"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE matches 
        SET status=%s, updated_at=CURRENT_TIMESTAMP
        WHERE client_id=%s AND captain_id=%s AND status != 'completed'
        RETURNING id
    """, (status, client_id, captain_id))
    
    result = cur.fetchone()
    
    if status == "in_progress":
        cur.execute("UPDATE users SET is_available=FALSE WHERE user_id=%s", (captain_id,))
    elif status in ["rejected", "cancelled", "completed"]:
        cur.execute("UPDATE users SET is_available=TRUE WHERE user_id=%s", (captain_id,))

    conn.commit()
    match_id = result['id'] if result else None
    cur.close()
    conn.close()
    return match_id

def get_match_details(client_id, captain_id):
    """جلب تفاصيل الطلب"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM matches 
        WHERE client_id=%s AND captain_id=%s 
        ORDER BY created_at DESC LIMIT 1
    """, (client_id, captain_id))
    match = cur.fetchone()
    cur.close()
    conn.close()
    return match

def save_rating(match_id, client_id, captain_id, rating, comment, notes):
    """حفظ التقييم مع الملاحظات - تم إصلاحه"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO ratings (match_id, client_id, captain_id, rating, comment, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (match_id, client_id) DO UPDATE SET
                rating = EXCLUDED.rating,
                comment = EXCLUDED.comment,
                notes = EXCLUDED.notes,
                created_at = CURRENT_TIMESTAMP
        """, (match_id, client_id, captain_id, rating, comment, notes))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"خطأ في حفظ التقييم: {e}")
        return False
    finally:
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
                COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as active_trips,
                COALESCE(AVG(r.rating), 0) as avg_rating
            FROM matches m
            LEFT JOIN ratings r ON m.id = r.match_id
            WHERE m.captain_id = %s
        """, (user_id,))
    
    stats = cur.fetchone()
    cur.close()
    conn.close()
    return stats

# إضافة جدول مؤقت لحفظ بيانات التقييم
rating_temp_data = {}

# ================== حالات التسجيل ==================
class RegisterStates(StatesGroup):
    role = State()
    subscription = State()
    full_name = State()
    phone = State()
    car_model = State()
    car_plate = State()
    agreement = State()
    city = State()
    neighborhood = State()
    neighborhood2 = State()
    neighborhood3 = State()

class RequestStates(StatesGroup):
    enter_destination = State()
    
class EditStates(StatesGroup):
    edit_name = State()
    edit_phone = State()
    edit_car_model = State()
    edit_car_plate = State()
    change_city = State()
    change_neighborhood = State()
    change_role = State()

class RatingStates(StatesGroup):
    rating_stars = State()
    rating_comment = State()
    rating_notes = State()

# ================== الأزرار الثابتة ==================
def get_main_keyboard(role):
    """لوحة المفاتيح الثابتة حسب نوع المستخدم"""
    keyboard = ReplyKeyboardBuilder()
    
    if role == "client":
        keyboard.button(text="🚕 طلب توصيلة")
        keyboard.button(text="📊 إحصائياتي")
        keyboard.button(text="⚙️ تعديل البيانات")
        keyboard.button(text="📞 اتصل بنا")
    else:  # captain
        keyboard.button(text="🟢 متاح للعمل")
        keyboard.button(text="🔴 غير متاح")
        keyboard.button(text="📊 إحصائياتي")
        keyboard.button(text="⚙️ تعديل البيانات")
        keyboard.button(text="📞 اتصل بنا")
    
    keyboard.adjust(2, 2, 1)
    return keyboard.as_markup(resize_keyboard=True)

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

def neighborhood_keyboard(city, selected_neighborhoods=None):
    """أزرار اختيار الحي"""
    try:
        with open("neighborhoods.json", "r", encoding="utf-8") as f:
            neighborhoods_data = json.load(f)
            
        builder = InlineKeyboardBuilder()
        selected = selected_neighborhoods or []
        
        for neighborhood in neighborhoods_data.get(city, []):
            if neighborhood not in selected:
                builder.button(text=neighborhood, callback_data=f"neigh_{neighborhood}")
        builder.adjust(2)
        return builder.as_markup()
        
    except FileNotFoundError:
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

def trip_control_keyboard(captain_id, client_id):
    """أزرار التحكم في الرحلة"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ تم الوصول - إنهاء الرحلة", callback_data=f"complete_trip_{captain_id}_{client_id}")
    return builder.as_markup()

def contact_keyboard(username, text="💬 تواصل"):
    """زر التواصل"""
    builder = InlineKeyboardBuilder()
    if username:
        builder.button(text=text, url=f"https://t.me/{username}")
    return builder.as_markup()

def rating_keyboard():
    """أزرار التقييم"""
    builder = InlineKeyboardBuilder()
    for i in range(1, 6):
        builder.button(text=f"{'⭐' * i}", callback_data=f"rate_{i}")
    builder.adjust(1)
    return builder.as_markup()

def edit_profile_keyboard(role):
    """أزرار تعديل البيانات"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="👤 الاسم", callback_data="edit_name")
    builder.button(text="📱 الجوال", callback_data="edit_phone")
    
    if role == "captain":
        builder.button(text="🚘 السيارة", callback_data="edit_car")
        builder.button(text="📍 المناطق", callback_data="edit_neighborhoods")
    
    builder.button(text="🌆 المدينة", callback_data="edit_city")
    builder.button(text="🔄 تغيير الدور", callback_data="change_role")
    builder.adjust(2)
    return builder.as_markup()

# ================== إعداد البوت ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================== معالجات الرسائل النصية (الأزرار الثابتة) ==================

@dp.message(F.text == "🚕 طلب توصيلة")
async def request_ride_text(message: types.Message, state: FSMContext):
    """طلب توصيلة عبر الزر الثابت"""
    user = get_user_by_id(message.from_user.id)
    if not user:
        await message.answer("❌ يجب التسجيل أولاً")
        return
    
    await message.answer(
        f"📍 موقعك الحالي: {user['city']} - {user['neighborhood']}\n\n"
        f"🎯 اكتب اسم المنطقة أو المكان الذي تريد الذهاب إليه:",
        reply_markup=get_main_keyboard(user['role'])
    )
    await state.set_state(RequestStates.enter_destination)

@dp.message(F.text == "🟢 متاح للعمل")
async def set_available_text(message: types.Message):
    """تعيين الكابتن متاح عبر الزر الثابت"""
    user = get_user_by_id(message.from_user.id)
    if not user:
        await message.answer("❌ يجب التسجيل أولاً")
        return
        
    update_user_field(message.from_user.id, "is_available", True)
    await message.answer(
        "🟢 تم تعيينك كمتاح للتوصيل!\n\n"
        "سيتم إشعارك عند وصول طلبات جديدة...",
        reply_markup=get_main_keyboard(user['role'])
    )

@dp.message(F.text == "🔴 غير متاح")
async def set_unavailable_text(message: types.Message):
    """تعيين الكابتن غير متاح عبر الزر الثابت"""
    user = get_user_by_id(message.from_user.id)
    if not user:
        await message.answer("❌ يجب التسجيل أولاً")
        return
        
    update_user_field(message.from_user.id, "is_available", False)
    await message.answer(
        "🔴 تم تعيينك كغير متاح للتوصيل\n\n"
        "لن تصلك طلبات جديدة حتى تقوم بتفعيل الحالة مرة أخرى",
        reply_markup=get_main_keyboard(user['role'])
    )

@dp.message(F.text == "📊 إحصائياتي")
async def show_stats_text(message: types.Message):
    """عرض الإحصائيات عبر الزر الثابت"""
    user = get_user_by_id(message.from_user.id)
    stats = get_user_stats(message.from_user.id)
    
    if not user or not stats:
        await message.answer("❌ لا توجد إحصائيات", reply_markup=get_main_keyboard(user['role'] if user else 'client'))
        return
    
    if user['role'] == 'client':
        stats_text = f"""
📊 إحصائياتك كعميل:

🔢 إجمالي الطلبات: {stats['total_requests']}
✅ الرحلات المكتملة: {stats['completed_trips']}
⏳ الطلبات المعلقة: {stats['pending_requests']}
        """
    else:
        avg_rating = round(float(stats['avg_rating']), 1) if stats['avg_rating'] else 0
        stats_text = f"""
📊 إحصائياتك ككابتن:

🔢 إجمالي الطلبات: {stats['total_requests']}
✅ الرحلات المكتملة: {stats['completed_trips']}
🚗 الرحلات النشطة: {stats['active_trips']}
⭐ متوسط التقييم: {avg_rating}/5
🔄 حالتك: {"متاح" if user['is_available'] else "غير متاح"}
        """
    
    await message.answer(stats_text, reply_markup=get_main_keyboard(user['role']))

@dp.message(F.text == "⚙️ تعديل البيانات")
async def edit_profile_text(message: types.Message):
    """تعديل البيانات عبر الزر الثابت"""
    user = get_user_by_id(message.from_user.id)
    if not user:
        await message.answer("❌ يجب التسجيل أولاً")
        return
    
    profile_info = f"""
👤 بياناتك الحالية:

📛 الاسم: {user['full_name']}
📱 الجوال: {user['phone']}
📍 المدينة: {user['city']}
    """
    
    if user['role'] == 'captain':
        profile_info += f"""
🚘 السيارة: {user['car_model']}
🔢 اللوحة: {user['car_plate']}
📍 مناطق العمل:
• {user['neighborhood']}
• {user['neighborhood2']}  
• {user['neighborhood3']}
        """
    else:
        profile_info += f"🏘️ الحي: {user['neighborhood']}"
    
    profile_info += "\n\nاختر البيان الذي تريد تعديله:"
    
    await message.answer(
        profile_info,
        reply_markup=edit_profile_keyboard(user['role'])
    )

@dp.message(F.text == "📞 اتصل بنا")
async def contact_us_text(message: types.Message):
    """معلومات التواصل عبر الزر الثابت"""
    user = get_user_by_id(message.from_user.id)
    contact_info = """
📞 للتواصل والاستفسارات:

📱 الجوال: 0501234567
📧 البريد: support@darbak.com
⏰ ساعات العمل: 24/7

💡 يمكنك أيضاً إرسال استفسارك هنا وسنرد عليك قريباً
    """
    
    await message.answer(contact_info, reply_markup=get_main_keyboard(user['role'] if user else 'client'))

# ================== معالجات بداية التسجيل ==================

@dp.message(F.text == "/start")
async def start_command(message: types.Message, state: FSMContext):
    """بداية التسجيل أو عرض القائمة الرئيسية"""
    await state.clear()
    user_id = message.from_user.id
    
    if is_user_registered(user_id):
        user = get_user_by_id(user_id)
        role_text = "العميل" if user['role'] == 'client' else "الكابتن"
        
        welcome_back = f"""
🎉 مرحباً {user['full_name']}!

أنت مسجل كـ {role_text} في:
📍 {user['city']} - {user['neighborhood']}

استخدم الأزرار أدناه للتنقل:
        """
        
        await message.answer(welcome_back, reply_markup=get_main_keyboard(user['role']))
    else:
        welcome_text = """
🌟 مرحباً بك في نظام دربك للمواصلات 🌟

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
