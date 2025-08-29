import psycopg2
from psycopg2 import sql
from config import PG_DB, PG_USER, PG_PASSWORD, PG_HOST, PG_PORT

def get_conn():
    return psycopg2.connect(
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        host=PG_HOST,
        port=PG_PORT
    )

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    
    # جدول المستخدمين
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
            city TEXT,
            neighborhood TEXT,
            available BOOLEAN DEFAULT TRUE,
            agreement BOOLEAN DEFAULT FALSE,
            username TEXT
        );
    """)
    
    # جدول المطابقات
    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id SERIAL PRIMARY KEY,
            client_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
            captain_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
            status VARCHAR(20) DEFAULT 'pending',
            CONSTRAINT unique_match UNIQUE (client_id, captain_id)
        );
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    print("✅ قاعدة البيانات جاهزة!")

# حفظ مستخدم جديد أو تحديثه
def save_user(user_id, data):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (user_id, role, subscription, full_name, phone, car_model, car_plate, seats, city, neighborhood, available, agreement, username)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (user_id) DO UPDATE SET
            role=EXCLUDED.role,
            subscription=EXCLUDED.subscription,
            full_name=EXCLUDED.full_name,
            phone=EXCLUDED.phone,
            car_model=EXCLUDED.car_model,
            car_plate=EXCLUDED.car_plate,
            seats=EXCLUDED.seats,
            city=EXCLUDED.city,
            neighborhood=EXCLUDED.neighborhood,
            available=EXCLUDED.available,
            agreement=EXCLUDED.agreement,
            username=EXCLUDED.username
    """, (
        user_id,
        data.get("role"),
        data.get("subscription"),
        data.get("full_name"),
        data.get("phone"),
        data.get("car_model"),
        data.get("car_plate"),
        data.get("seats"),
        data.get("city"),
        data.get("neighborhood"),
        data.get("available", True),
        data.get("agreement", False),
        data.get("username")
    ))
    conn.commit()
    cur.close()
    conn.close()

# البحث عن الكباتن المتاحين في نفس المدينة والحي
def find_captains(city, neighborhood):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, full_name, phone, username FROM users
        WHERE role='captain' AND city=%s AND neighborhood=%s AND available=TRUE
    """, (city, neighborhood))
    result = cur.fetchall()
    conn.close()
    # ارجع قائمة من القواميس
    return [{"user_id": r[0], "full_name": r[1], "phone": r[2], "username": r[3]} for r in result]

# تحديث حالة المطابقة
def update_match(client_id, captain_id, status):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO matches (client_id, captain_id, status)
        VALUES (%s, %s, %s)
        ON CONFLICT (client_id, captain_id) DO UPDATE SET status=EXCLUDED.status
    """, (client_id, captain_id, status))
    conn.commit()
    cur.close()
    conn.close()
