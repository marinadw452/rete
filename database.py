import psycopg2
import psycopg2.extras
from config import PG_DB, PG_USER, PG_PASSWORD, PG_HOST, PG_PORT

def get_conn():
    return psycopg2.connect(
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        host=PG_HOST,
        port=PG_PORT,
        cursor_factory=psycopg2.extras.RealDictCursor
    )

# ================== إضافة/تحديث مستخدم ==================
def add_user(user_data: dict):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (user_id, role, subscription, full_name, phone, car_model, car_plate, seats, city, neighborhood)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (user_id) DO UPDATE SET
            role = EXCLUDED.role,
            subscription = EXCLUDED.subscription,
            full_name = EXCLUDED.full_name,
            phone = EXCLUDED.phone,
            car_model = EXCLUDED.car_model,
            car_plate = EXCLUDED.car_plate,
            seats = EXCLUDED.seats,
            city = EXCLUDED.city,
            neighborhood = EXCLUDED.neighborhood
    """, (
        user_data["user_id"],
        user_data["role"],
        user_data["subscription"],
        user_data["full_name"],
        user_data["phone"],
        user_data.get("car_model"),
        user_data.get("car_plate"),
        user_data.get("seats"),
        user_data.get("city"),
        user_data.get("neighborhood")
    ))
    conn.commit()
    cur.close()
    conn.close()

# ================== جلب جميع الكباتن المتاحين ==================
def get_available_captains(city: str, neighborhood: str, client_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM users
        WHERE role='captain' 
          AND is_available=TRUE
          AND city=%s 
          AND neighborhood=%s
          AND user_id NOT IN (
              SELECT captain_id FROM matches WHERE client_id=%s AND status='rejected'
          )
    """, (city, neighborhood, client_id))
    captains = cur.fetchall()
    cur.close()
    conn.close()
    return captains

# ================== تحديث حالة المطابقة ==================
def update_match(client_id: int, captain_id: int, status: str):
    conn = get_conn()
    cur = conn.cursor()
    # إذا قبل العميل الكابتن
    if status == "accepted":
        cur.execute("UPDATE users SET is_available=FALSE WHERE user_id=%s", (captain_id,))
    cur.execute("""
        INSERT INTO matches (client_id, captain_id, status)
        VALUES (%s, %s, %s)
    """, (client_id, captain_id, status))
    conn.commit()
    cur.close()
    conn.close()
print("✅ الجداول جاهزة")
