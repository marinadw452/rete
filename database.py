import psycopg2
import psycopg2.extras
from config import PG_DB, PG_USER, PG_PASSWORD, PG_HOST, PG_PORT
from aiogram import types
from aiogram.fsm.context import FSMContext
from main import dp  # تأكد أن dp مستورد من ملف البوت الرئيسي

def get_conn():
    return psycopg2.connect(
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        host=PG_HOST,
        port=PG_PORT,
        cursor_factory=psycopg2.extras.RealDictCursor
    )

# ================== إضافة مستخدم ==================
def add_user(user_data: dict):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (user_id, role, subscription, full_name, phone, car_model, car_plate, seats)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (user_id) DO NOTHING
    """, (
        user_data["user_id"],
        user_data["role"],
        user_data["subscription"],
        user_data["full_name"],
        user_data["phone"],
        user_data.get("car_model"),
        user_data.get("car_plate"),
        user_data.get("seats")
    ))
    conn.commit()
    cur.close()
    conn.close()

# ================== جلب جميع الكباتن المتاحين ==================
def get_available_captains(city: str, neighborhood: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM users
        WHERE role='captain' AND is_available=TRUE
    """)
    captains = cur.fetchall()
    cur.close()
    conn.close()
    return captains

# ================== قبول/رفض الكابتن ==================
@dp.callback_query()
async def captain_decision_handler(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data
    client_id = callback.from_user.id  # العميل الحالي

    if data.startswith("accept_") or data.startswith("reject_"):
        captain_id = int(data.split("_")[1])
        conn = get_conn()
        cursor = conn.cursor()

        if data.startswith("accept_"):
            # جعل الكابتن غير متاح
            cursor.execute("UPDATE users SET is_available=FALSE WHERE user_id=%s", (captain_id,))
            
            # تسجيل المطابقة
            cursor.execute("""
                INSERT INTO matches (client_id, captain_id, status)
                VALUES (%s, %s, 'accepted')
            """, (client_id, captain_id))
            conn.commit()
            
            await callback.message.answer("✅ تم قبول الكابتن، بياناته مرسلة للعميل.")
        else:
            # تسجيل رفض العميل للكابتن
            cursor.execute("""
                INSERT INTO matches (client_id, captain_id, status)
                VALUES (%s, %s, 'rejected')
            """, (client_id, captain_id))
            conn.commit()

            await callback.message.answer("❌ تم رفض الكابتن. يمكنك اختيار كابتن آخر.")

        cursor.close()
        conn.close()
