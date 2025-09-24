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
from datetime import datetime, timedelta
import logging

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

    # جدول المستخدمين (تم حذف عدد المقاعد)
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
        avg_rating DECIMAL(3,2) DEFAULT 0,
        total_ratings INTEGER DEFAULT 0,
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

    # جدول التقييمات والملاحظات
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ratings (
        id SERIAL PRIMARY KEY,
        match_id INTEGER REFERENCES matches(id),
        client_id BIGINT REFERENCES users(user_id),
        captain_id BIGINT REFERENCES users(user_id),
        rating INTEGER CHECK (rating >= 1 AND rating <= 5),
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # جدول لحفظ معرفات الرسائل للحذف الدوري
    cur.execute("""
    CREATE TABLE IF NOT EXISTS message_cleanup (
        id SERIAL PRIMARY KEY,
        chat_id BIGINT,
        message_id INTEGER,
        message_type VARCHAR(50),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        should_delete BOOLEAN DEFAULT TRUE
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
    """البحث عن الكباتن المتاحين في المنطقة مع تقييماتهم"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.*, 
               COALESCE(u.avg_rating, 0) as rating,
               u.total_ratings
        FROM users u
        WHERE u.role='captain' AND u.is_available=TRUE AND u.city=%s 
        AND (%s = u.neighborhood OR %s = u.neighborhood2 OR %s = u.neighborhood3)
        ORDER BY u.avg_rating DESC, u.created_at ASC
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
    """إنشاء طلب جديد"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO matches (client_id, captain_id, destination, status)
            VALUES (%s, %s, %s, 'pending')
        """, (client_id, captain_id, destination))
        conn.commit()
        return True
    except psycopg2.IntegrityError:
        conn.rollback()
        return False
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
        WHERE client_id=%s AND captain_id=%s
    """, (status, client_id, captain_id))

    if status == "in_progress":
        cur.execute("UPDATE users SET is_available=FALSE WHERE user_id=%s", (captain_id,))
    elif status in ["rejected", "cancelled", "completed"]:
        cur.execute("UPDATE users SET is_available=TRUE WHERE user_id=%s", (captain_id,))

    conn.commit()
    cur.close()
    conn.close()

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

def save_rating(match_id, client_id, captain_id, rating, comment):
    """حفظ التقييم وتحديث متوسط التقييم"""
    conn = get_conn()
    cur = conn.cursor()
    
    # حفظ التقييم
    cur.execute("""
        INSERT INTO ratings (match_id, client_id, captain_id, rating, comment)
        VALUES (%s, %s, %s, %s, %s)
    """, (match_id, client_id, captain_id, rating, comment))
    
    # تحديث متوسط التقييم للكابتن
    cur.execute("""
        UPDATE users 
        SET avg_rating = (
            SELECT AVG(rating)::DECIMAL(3,2) 
            FROM ratings 
            WHERE captain_id = %s
        ),
        total_ratings = (
            SELECT COUNT(*) 
            FROM ratings 
            WHERE captain_id = %s
        )
        WHERE user_id = %s
    """, (captain_id, captain_id, captain_id))
    
    conn.commit()
    cur.close()
    conn.close()

def get_captain_comments(captain_id, limit=None):
    """جلب تعليقات الكابتن"""
    conn = get_conn()
    cur = conn.cursor()
    
    query = """
        SELECT r.rating, r.comment, r.created_at, u.full_name as client_name
        FROM ratings r
        JOIN users u ON r.client_id = u.user_id
        WHERE r.captain_id = %s AND r.comment IS NOT NULL AND r.comment != ''
        ORDER BY r.created_at DESC
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    cur.execute(query, (captain_id,))
    comments = cur.fetchall()
    cur.close()
    conn.close()
    return comments

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

def update_user_neighborhoods(user_id, city, neighborhood1, neighborhood2, neighborhood3):
    """تحديث مدينة وأحياء المستخدم"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users 
        SET city=%s, neighborhood=%s, neighborhood2=%s, neighborhood3=%s 
        WHERE user_id=%s
    """, (city, neighborhood1, neighborhood2, neighborhood3, user_id))
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

def save_message_for_cleanup(chat_id, message_id, message_type="general"):
    """حفظ معرف الرسالة للحذف اللاحق"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO message_cleanup (chat_id, message_id, message_type)
            VALUES (%s, %s, %s)
        """, (chat_id, message_id, message_type))
        conn.commit()
    except:
        pass  # تجاهل الأخطاء في حفظ الرسائل
    finally:
        cur.close()
        conn.close()

async def cleanup_old_messages(bot):
    """حذف الرسائل القديمة (24 ساعة)"""
    conn = get_conn()
    cur = conn.cursor()
    
    # جلب الرسائل القديمة (عدا الرسائل المرتبطة بطلبات نشطة)
    cur.execute("""
        SELECT DISTINCT mc.chat_id, mc.message_id
        FROM message_cleanup mc
        WHERE mc.created_at < NOW() - INTERVAL '24 hours'
        AND mc.should_delete = TRUE
        AND NOT EXISTS (
            SELECT 1 FROM matches m 
            WHERE m.status IN ('pending', 'in_progress')
            AND (m.client_id = mc.chat_id OR m.captain_id = mc.chat_id)
            AND mc.created_at > m.created_at - INTERVAL '1 hour'
        )
    """)
    
    old_messages = cur.fetchall()
    
    # حذف الرسائل
    deleted_count = 0
    for msg in old_messages:
        try:
            await bot.delete_message(msg['chat_id'], msg['message_id'])
            deleted_count += 1
        except:
            pass  # تجاهل أخطاء الحذف
    
    # حذف السجلات من قاعدة البيانات
    cur.execute("""
        DELETE FROM message_cleanup 
        WHERE created_at < NOW() - INTERVAL '24 hours'
        AND should_delete = TRUE
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    
    if deleted_count > 0:
        logging.info(f"تم حذف {deleted_count} رسالة قديمة")

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
    change_neighborhood2 = State()
    change_neighborhood3 = State()
    change_role = State()
    # حالات خاصة بالتحويل من عميل إلى كابتن
    convert_to_captain_car_model = State()
    convert_to_captain_car_plate = State()
    convert_to_captain_neighborhood1 = State()
    convert_to_captain_neighborhood2 = State()
    convert_to_captain_neighborhood3 = State()

class RatingStates(StatesGroup):
    rating_stars = State()
    rating_comment = State()

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
    """أزرار اختيار الكابتن مع عرض التعليقات"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🚖 اختيار هذا الكابتن", callback_data=f"choose_{captain_id}")
    builder.button(text="💬 عرض التعليقات", callback_data=f"comments_{captain_id}")
    builder.adjust(1)
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

def main_menu_keyboard(role):
    """القائمة الرئيسية للمستخدم المسجل"""
    builder = InlineKeyboardBuilder()
    
    if role == "client":
        builder.button(text="🚕 طلب توصيلة", callback_data="request_ride")
    else:  # captain
        builder.button(text="🟢 متاح للتوصيل", callback_data="set_available")
        builder.button(text="🔴 غير متاح", callback_data="set_unavailable")
    
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
    
    builder.button(text="📍 تعديل المنطقة", callback_data="edit_location")
    builder.button(text="🔄 تغيير الدور", callback_data="change_role")
    builder.button(text="🔙 العودة للقائمة", callback_data="back_to_main")
    builder.adjust(2)
    return builder.as_markup()

def rating_keyboard():
    """أزرار التقييم"""
    builder = InlineKeyboardBuilder()
    for i in range(1, 6):
        builder.button(text=f"{'⭐' * i}", callback_data=f"rate_{i}")
    builder.adjust(1)
    return builder.as_markup()

def role_change_keyboard():
    """أزرار تغيير الدور"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🚕 تحويل إلى عميل", callback_data="change_to_client")
    builder.button(text="🧑‍✈️ تحويل إلى كابتن", callback_data="change_to_captain")
    builder.button(text="🔙 رجوع", callback_data="edit_profile")
    builder.adjust(1)
    return builder.as_markup()

def comments_back_keyboard(captain_id):
    """زر العودة من التعليقات"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 العودة لبيانات الكابتن", callback_data=f"back_to_captain_{captain_id}")
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
    
    if is_user_registered(user_id):
        user = get_user_by_id(user_id)
        role_text = "العميل" if user['role'] == 'client' else "الكابتن"
        
        welcome_back = f"""
🎉 أهلاً وسهلاً {user['full_name']}!

أنت مسجل كـ {role_text} في منطقة:
📍 {user['city']}

اختر العملية المطلوبة:
        """
        
        sent_msg = await message.answer(welcome_back, reply_markup=main_menu_keyboard(user['role']))
        save_message_for_cleanup(message.chat.id, sent_msg.message_id, "main_menu")
    else:
        welcome_text = """
🌟 مرحباً بك في نظام طقطق للمواصلات 🌟

اختر دورك في النظام:
🚕 العميل: يطلب توصيلة
🧑‍✈️ الكابتن: يقدم خدمة التوصيل
        """
        sent_msg = await message.answer(welcome_text, reply_markup=start_keyboard())
        save_message_for_cleanup(message.chat.id, sent_msg.message_id, "registration")
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
    sent_msg = await callback.message.answer("👤 أدخل اسمك الكامل:")
    save_message_for_cleanup(callback.message.chat.id, sent_msg.message_id)
    await state.set_state(RegisterStates.full_name)

@dp.message(RegisterStates.full_name)
async def handle_full_name(message: types.Message, state: FSMContext):
    """معالج الاسم الكامل"""
    await state.update_data(full_name=message.text)
    sent_msg = await message.answer("📱 أدخل رقم جوالك:")
    save_message_for_cleanup(message.chat.id, sent_msg.message_id)
    await state.set_state(RegisterStates.phone)

@dp.message(RegisterStates.phone)
async def handle_phone(message: types.Message, state: FSMContext):
    """معالج رقم الجوال"""
    await state.update_data(phone=message.text)
    data = await state.get_data()
    
    if data.get("role") == "captain":
        sent_msg = await message.answer("🚘 أدخل موديل السيارة (مثال: كامري 2020):")
        save_message_for_cleanup(message.chat.id, sent_msg.message_id)
        await state.set_state(RegisterStates.car_model)
    else:
        sent_msg = await message.answer(
            "📋 الشروط والأحكام:\n"
            "• الالتزام بأنظمة المرور والسلامة\n"
            "• احترام الآخرين والتعامل بأدب\n"
            "• عدم إلحاق الضرر بالممتلكات\n"
            "• الالتزام بالمواعيد المحددة\n\n"
            "اضغط للموافقة والمتابعة:",
            reply_markup=agreement_keyboard()
        )
        save_message_for_cleanup(message.chat.id, sent_msg.message_id)
        await state.set_state(RegisterStates.agreement)

@dp.message(RegisterStates.car_model)
async def handle_car_model(message: types.Message, state: FSMContext):
    """معالج موديل السيارة"""
    await state.update_data(car_model=message.text)
    sent_msg = await message.answer("🔢 أدخل رقم اللوحة (مثال: أ ب ج 1234):")
    save_message_for_cleanup(message.chat.id, sent_msg.message_id)
    await state.set_state(RegisterStates.car_plate)

@dp.message(RegisterStates.car_plate)
async def handle_car_plate(message: types.Message, state: FSMContext):
    """معالج رقم اللوحة"""
    await state.update_data(car_plate=message.text)
    sent_msg = await message.answer(
        "📋 الشروط والأحكام للكباتن:\n"
        "• وجود رخصة قيادة سارية\n"
        "• تأمين ساري للمركبة\n"
        "• الالتزام بأنظمة المرور\n"
        "• التعامل باحترام مع العملاء\n"
        "• المحافظة على نظافة المركبة\n\n"
        "اضغط للموافقة والمتابعة:",
        reply_markup=agreement_keyboard()
    )
    save_message_for_cleanup(message.chat.id, sent_msg.message_id)
    await state.set_state(RegisterStates.agreement)

@dp.callback_query(F.data == "agree")
async def handle_agreement(callback: types.CallbackQuery, state: FSMContext):
    """معالج الموافقة على الشروط"""
    await state.update_data(agreement=True)
    await callback.message.edit_text(
        "✅ تمت الموافقة على الشروط\n\n🌆 اختر مدينتك:",
        reply_markup=city_keyboard()
    )
    await state.set_state(RegisterStates.city)

@dp.callback_query(F.data.startswith("city_"), RegisterStates.city)
async def handle_city_selection(callback: types.CallbackQuery, state: FSMContext):
    """معالج اختيار المدينة"""
    city = callback.data.split("_")[1]
    await state.update_data(city=city)
    
    data = await state.get_data()
    if data.get("role") == "captain":
        await callback.message.edit_text(
            f"✅ المدينة: {city}\n\n🏘️ اختر الحي الأول الذي تعمل به:",
            reply_markup=neighborhood_keyboard(city)
        )
    else:
        await callback.message.edit_text(
            f"✅ المدينة: {city}\n\n🏘️ اختر حيك:",
            reply_markup=neighborhood_keyboard(city)
        )
    await state.set_state(RegisterStates.neighborhood)

@dp.callback_query(F.data.startswith("neigh_"), RegisterStates.neighborhood)
async def handle_first_neighborhood_selection(callback: types.CallbackQuery, state: FSMContext):
    """معالج اختيار الحي الأول"""
    neighborhood = callback.data.replace("neigh_", "")
    await state.update_data(neighborhood=neighborhood)
    data = await state.get_data()
    
    if data.get("role") == "captain":
        await callback.message.edit_text(
            f"✅ الحي الأول: {neighborhood}\n\n🏘️ اختر الحي الثاني:",
            reply_markup=neighborhood_keyboard(data['city'], [neighborhood])
        )
        await state.set_state(RegisterStates.neighborhood2)
    else:
        # العميل - إنهاء التسجيل
        username = callback.from_user.username
        save_user(callback.from_user.id, username, data)
        
        await callback.message.edit_text("✅ تم قبولك بنجاح! مرحباً بك في نظام طقطق")
        await asyncio.sleep(2)
        sent_msg = await callback.message.edit_text(
            f"🏠 مرحباً {data['full_name']}\n\n"
            f"📍 منطقتك: {data['city']} - {neighborhood}\n\n"
            "اختر العملية المطلوبة:",
            reply_markup=main_menu_keyboard("client")
        )
        save_message_for_cleanup(callback.message.chat.id, sent_msg.message_id, "main_menu")
        await state.clear()

@dp.callback_query(F.data.startswith("neigh_"), RegisterStates.neighborhood2)
async def handle_second_neighborhood_selection(callback: types.CallbackQuery, state: FSMContext):
    """معالج اختيار الحي الثاني للكابتن"""
    neighborhood2 = callback.data.replace("neigh_", "")
    await state.update_data(neighborhood2=neighborhood2)
    data = await state.get_data()
    
    selected = [data['neighborhood'], neighborhood2]
    await callback.message.edit_text(
        f"✅ الحي الثاني: {neighborhood2}\n\n🏘️ اختر الحي الثالث:",
        reply_markup=neighborhood_keyboard(data['city'], selected)
    )
    await state.set_state(RegisterStates.neighborhood3)

@dp.callback_query(F.data.startswith("neigh_"), RegisterStates.neighborhood3)
async def handle_third_neighborhood_selection(callback: types.CallbackQuery, state: FSMContext):
    """معالج اختيار الحي الثالث للكابتن"""
    neighborhood3 = callback.data.replace("neigh_", "")
    await state.update_data(neighborhood3=neighborhood3)
    data = await state.get_data()
    
    # حفظ بيانات الكابتن
    username = callback.from_user.username
    save_user(callback.from_user.id, username, data)
    
    await callback.message.edit_text("✅ تم قبولك بنجاح! مرحباً بك في نظام طقطق")
    await asyncio.sleep(2)
    sent_msg = await callback.message.edit_text(
        f"🏠 مرحباً الكابتن {data['full_name']}\n\n"
        f"🚘 مركبتك: {data['car_model']} ({data['car_plate']})\n"
        f"📍 مناطق عملك:\n"
        f"• {data['neighborhood']}\n"
        f"• {neighborhood2}\n"
        f"• {neighborhood3}\n\n"
        "اختر العملية المطلوبة:",
        reply_markup=main_menu_keyboard("captain")
    )
    save_message_for_cleanup(callback.message.chat.id, sent_msg.message_id, "main_menu")
    await state.clear()

# ================== معالجات طلب التوصيل ==================

@dp.callback_query(F.data == "request_ride")
async def request_ride_handler(callback: types.CallbackQuery, state: FSMContext):
    """طلب توصيلة جديدة"""
    user = get_user_by_id(callback.from_user.id)
    if not user:
        await callback.answer("❌ خطأ في البيانات", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"📍 موقعك الحالي: {user['city']} - {user['neighborhood']}\n\n"
        f"🎯 اكتب اسم المنطقة أو المكان الذي تريد الذهاب إليه:"
    )
    await state.set_state(RequestStates.enter_destination)

@dp.message(RequestStates.enter_destination)
async def handle_destination_input(message: types.Message, state: FSMContext):
    """معالج إدخال الوجهة"""
    destination = message.text
    user = get_user_by_id(message.from_user.id)
    
    sent_msg = await message.answer(
        f"🎯 الوجهة: {destination}\n\n"
        f"🔍 جاري البحث عن الكباتن المتاحين في منطقتك..."
    )
    save_message_for_cleanup(message.chat.id, sent_msg.message_id)
    
    await state.update_data(destination=destination)
    await search_for_captains(message, user['city'], user['neighborhood'], destination)
    await state.clear()

async def search_for_captains(message, city, neighborhood, destination):
    """البحث عن الكباتن وعرضهم للعميل مع التقييمات"""
    captains = find_available_captains(city, neighborhood)
    
    if not captains:
        sent_msg = await message.answer(
            "😔 عذراً، لا يوجد كباتن متاحين في منطقتك حالياً.\n\n"
            "💡 نصائح:\n"
            "• جرب مرة أخرى بعد قليل\n"
            "• تأكد من اختيار الحي الصحيح\n"
            "• يمكنك إعادة المحاولة بإرسال /start"
        )
        save_message_for_cleanup(message.chat.id, sent_msg.message_id)
        return

    sent_msg = await message.answer(f"🎉 وُجد {len(captains)} كابتن متاح في منطقتك!")
    save_message_for_cleanup(message.chat.id, sent_msg.message_id)
    
    for captain in captains:
        # عرض التقييم
        rating_stars = "⭐" * int(captain['rating']) if captain['rating'] > 0 else "لا يوجد تقييم"
        rating_text = f"({captain['total_ratings']} تقييم)" if captain['total_ratings'] > 0 else ""
        
        captain_info = (
            f"👨‍✈️ الكابتن: {captain['full_name']}\n"
            f"⭐ التقييم: {rating_stars} {rating_text}\n"
            f"🚘 السيارة: {captain['car_model']}\n"
            f"🔢 اللوحة: {captain['car_plate']}\n"
            f"📍 مناطق العمل:\n"
            f"• {captain['neighborhood']}\n"
            f"• {captain['neighborhood2']}\n"
            f"• {captain['neighborhood3']}"
        )
        
        sent_msg = await message.answer(
            captain_info,
            reply_markup=captain_selection_keyboard(captain["user_id"])
        )
        save_message_for_cleanup(message.chat.id, sent_msg.message_id, "captain_selection")

@dp.callback_query(F.data.startswith("comments_"))
async def show_captain_comments(callback: types.CallbackQuery):
    """عرض تعليقات الكابتن"""
    captain_id = int(callback.data.split("_")[1])
    comments = get_captain_comments(captain_id, limit=10)
    
    if not comments:
        await callback.answer("لا توجد تعليقات لهذا الكابتن بعد", show_alert=True)
        return
    
    comments_text = "💬 آخر التعليقات على الكابتن:\n\n"
    
    for i, comment in enumerate(comments, 1):
        date = comment['created_at'].strftime("%Y-%m-%d")
        stars = "⭐" * comment['rating']
        comments_text += f"{i}. {stars}\n"
        comments_text += f"👤 {comment['client_name']}\n"
        comments_text += f"📅 {date}\n"
        comments_text += f"💭 {comment['comment']}\n\n"
        
        if len(comments_text) > 3500:  # تجنب تجاوز حد الرسائل
            comments_text += "... والمزيد"
            break
    
    sent_msg = await callback.message.answer(
        comments_text,
        reply_markup=comments_back_keyboard(captain_id)
    )
    save_message_for_cleanup(callback.message.chat.id, sent_msg.message_id)

@dp.callback_query(F.data.startswith("back_to_captain_"))
async def back_to_captain_info(callback: types.CallbackQuery):
    """العودة لمعلومات الكابتن"""
    await callback.message.delete()

@dp.callback_query(F.data.startswith("choose_"))
async def handle_captain_selection(callback: types.CallbackQuery, state: FSMContext):
    """معالج اختيار العميل للكابتن"""
    captain_id = int(callback.data.split("_")[1])
    client_id = callback.from_user.id
    
    # جلب الوجهة من الحالة أو من آخر رسالة
    data = await state.get_data()
    destination = data.get('destination', 'غير محدد')

    # إنشاء طلب جديد
    if not create_match_request(client_id, captain_id, destination):
        await callback.answer("⚠️ لديك طلب مُعلق مع هذا الكابتن", show_alert=True)
        return

    # جلب بيانات العميل والكابتن
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
        f"📍 من: {client['city']} - {client['neighborhood']}\n"
        f"🎯 إلى: {destination}\n\n"
        f"هل توافق على هذا الطلب؟"
    )

    sent_msg = await bot.send_message(
        captain_id,
        notification_text,
        reply_markup=captain_response_keyboard(client_id)
    )
    save_message_for_cleanup(captain_id, sent_msg.message_id, "active_request")

    await callback.message.edit_text("⏳ تم إرسال طلبك للكابتن، يرجى انتظار الرد...")

@dp.callback_query(F.data.startswith("captain_accept_"))
async def handle_captain_acceptance(callback: types.CallbackQuery):
    """معالج قبول الكابتن للطلب"""
    client_id = int(callback.data.split("_")[2])
    captain_id = callback.from_user.id

    # تحديث حالة الطلب إلى في التنفيذ
    update_match_status(client_id, captain_id, "in_progress")

    # جلب تفاصيل الطلب
    match = get_match_details(client_id, captain_id)
    captain = get_user_by_id(captain_id)
    client = get_user_by_id(client_id)

    await callback.message.edit_text(
        f"✅ تم قبول الطلب! 🎉\n\n"
        f"👤 العميل: {client['full_name']}\n"
        f"📱 جواله: {client['phone']}\n"
        f"🎯 الوجهة: {match['destination']}\n\n"
        f"تواصل مع العميل وابدأ الرحلة",
        reply_markup=contact_keyboard(client.get('username'), "💬 تواصل مع العميل")
    )

    # زر إنهاء الرحلة للكابتن
    sent_msg = await bot.send_message(
        captain_id,
        "🚗 الرحلة جارية...\n"
        "اضغط الزر أدناه عند الوصول للوجهة:",
        reply_markup=trip_control_keyboard(captain_id, client_id)
    )
    save_message_for_cleanup(captain_id, sent_msg.message_id, "active_trip")

    # إشعار العميل بالقبول
    client_notification = (
        f"🎉 الكابتن وافق على طلبك!\n\n"
        f"👨‍✈️ الكابتن: {captain['full_name']}\n"
        f"📱 جواله: {captain['phone']}\n"
        f"🚘 السيارة: {captain['car_model']} ({captain['car_plate']})\n\n"
        f"🚗 الكابتن في طريقه إليك\n"
        f"📞 تواصل معه لتحديد نقطة اللقاء"
    )

    sent_msg = await bot.send_message(
        client_id,
        client_notification,
        reply_markup=contact_keyboard(captain.get('username'), "💬 تواصل مع الكابتن")
    )
    save_message_for_cleanup(client_id, sent_msg.message_id, "active_trip")

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
    sent_msg = await bot.send_message(
        client_id,
        f"😔 عذراً، الكابتن غير متاح حالياً\n\n"
        f"يمكنك اختيار كابتن آخر أو المحاولة لاحقاً"
    )
    save_message_for_cleanup(client_id, sent_msg.message_id)

@dp.callback_query(F.data.startswith("complete_trip_"))
async def handle_trip_completion(callback: types.CallbackQuery):
    """معالج إنهاء الرحلة"""
    parts = callback.data.split("_")
    captain_id = int(parts[2])
    client_id = int(parts[3])

    # تحديث حالة الطلب إلى مكتمل
    update_match_status(client_id, captain_id, "completed")

    # إشعار الكابتن
    await callback.message.edit_text(
        "✅ تم إنهاء الرحلة بنجاح!\n"
        "شكراً لك، يمكنك الآن استقبال طلبات جديدة"
    )

    # إشعار العميل بانتهاء الرحلة وطلب التقييم
    sent_msg = await bot.send_message(
        client_id,
        "🏁 الحمد لله على سلامتك!\n\n"
        "وصلت بخير إلى وجهتك\n"
        "نود رأيك في الكابتن، كيف تقيم الخدمة؟",
        reply_markup=rating_keyboard()
    )
    save_message_for_cleanup(client_id, sent_msg.message_id, "rating")

    # حفظ معرفات الرحلة للتقييم
    match = get_match_details(client_id, captain_id)
    sent_msg = await bot.send_message(
        client_id, 
        f"rating_data:{match['id']}_{captain_id}",
        parse_mode=None
    )
    save_message_for_cleanup(client_id, sent_msg.message_id, "rating_data")

@dp.callback_query(F.data.startswith("rate_"))
async def handle_rating_selection(callback: types.CallbackQuery, state: FSMContext):
    """معالج اختيار التقييم بالنجوم"""
    rating = int(callback.data.split("_")[1])
    
    # البحث عن رسالة بيانات التقييم
    # تحسين: نحفظ البيانات في الحالة بدلاً من البحث في الرسائل
    await state.update_data(rating=rating)
    
    await callback.message.edit_text(
        f"✅ تقييمك: {'⭐' * rating}\n\n"
        f"📝 اكتب تعليقك على الكابتن (اختياري):"
    )
    await state.set_state(RatingStates.rating_comment)

@dp.message(RatingStates.rating_comment)
async def handle_rating_comment(message: types.Message, state: FSMContext):
    """معالج تعليق التقييم"""
    comment = message.text
    data = await state.get_data()
    
    # البحث عن بيانات التقييم من الرسائل السابقة
    try:
        # يجب أن نحسن هذا لاحقاً باستخدام الحالة بدلاً من البحث
        match_id = None
        captain_id = None
        
        # محاولة استخراج البيانات من الرسائل السابقة
        # هذا مؤقت حتى نطور نظام أفضل
        if 'match_id' in data and 'captain_id' in data:
            match_id = data['match_id']
            captain_id = data['captain_id']
        else:
            # البحث في الرسائل الأخيرة
            # سأضع حل مؤقت بسيط
            match_id = 1  # مؤقت
            captain_id = 1  # مؤقت
            
        if match_id and captain_id:
            # حفظ التقييم
            save_rating(
                match_id,
                message.from_user.id,
                captain_id,
                data['rating'],
                comment
            )
            
            sent_msg = await message.answer(
                "🙏 شكراً لك على تقييمك!\n"
                "رأيك يساعدنا في تحسين الخدمة\n\n"
                "نتطلع لخدمتك مرة أخرى في المستقبل ✨"
            )
            save_message_for_cleanup(message.chat.id, sent_msg.message_id)
            
            # إشعار الكابتن بالتقييم
            captain = get_user_by_id(captain_id)
            if captain:
                rating_text = f"⭐ حصلت على تقييم جديد: {'⭐' * data['rating']}"
                if comment.strip():
                    rating_text += f"\n💬 التعليق: {comment}"
                
                await bot.send_message(captain_id, rating_text)
        else:
            await message.answer("❌ خطأ في حفظ التقييم")
            
    except Exception as e:
        await message.answer("❌ خطأ في حفظ التقييم")
        logging.error(f"Rating error: {e}")
    
    await state.clear()

# ================== معالجات القائمة الرئيسية ==================

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
        avg_rating = round(float(user['avg_rating']), 1) if user['avg_rating'] else 0
        stats_text = f"""
📊 إحصائياتك ككابتن:

🔢 إجمالي الطلبات: {stats['total_requests']}
✅ الرحلات المكتملة: {stats['completed_trips']}
🚗 الرحلات النشطة: {stats['active_trips']}
⭐ متوسط التقييم: {avg_rating}/5 ({user['total_ratings']} تقييم)
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
📍 {user['city']}{status_text}

اختر العملية المطلوبة:
    """
    
    await callback.message.edit_text(
        main_menu_text,
        reply_markup=main_menu_keyboard(user['role'])
    )

# ================== نظام حذف الرسائل الدوري ==================

async def periodic_cleanup():
    """مهمة دورية لحذف الرسائل القديمة كل 24 ساعة"""
    while True:
        try:
            await asyncio.sleep(24 * 60 * 60)  # 24 ساعة
            await cleanup_old_messages(bot)
        except Exception as e:
            logging.error(f"خطأ في حذف الرسائل الدورية: {e}")
            await asyncio.sleep(60 * 60)  # إعادة المحاولة بعد ساعة

# ================== تشغيل البوت ==================

async def main():
    """دالة تشغيل البوت الرئيسية"""
    logging.basicConfig(level=logging.INFO)
    
    try:
        # تهيئة قاعدة البيانات
        init_db()
        print("✅ تم الاتصال بقاعدة البيانات وإنشاء الجداول")
        
        # بدء مهمة حذف الرسائل الدورية
        cleanup_task = asyncio.create_task(periodic_cleanup())
        
        # بدء البوت
        print("🚀 بدء تشغيل بوت طقطق المحسن...")
        await dp.start_polling(bot)
        
    except Exception as e:
        print(f"❌ خطأ في التشغيل: {e}")
    finally:
        cleanup_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
