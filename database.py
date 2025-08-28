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

def init_db():
    conn = get_conn()
    cur = conn.cursor()

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
        agreement BOOLEAN DEFAULT FALSE,
        city TEXT,
        neighborhood TEXT,
        available BOOLEAN DEFAULT TRUE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS matches (
        id SERIAL PRIMARY KEY,
        client_id BIGINT REFERENCES users(user_id),
        captain_id BIGINT REFERENCES users(user_id),
        status VARCHAR(20) DEFAULT 'pending'
    )
    """)

    conn.commit()
    cur.close()
    conn.close()

def save_user(user_id, data):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (user_id, role, subscription, full_name, phone, car_model, car_plate, seats, agreement, city, neighborhood, available)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE)
        ON CONFLICT (user_id) DO UPDATE SET
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
            available=TRUE
    """, (
        user_id,
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

def find_captains(city, neighborhood):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM users 
        WHERE role='captain' AND available=TRUE AND city=%s AND neighborhood=%s
    """, (city, neighborhood))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# database.py
def update_match(client_id, captain_id, status):
    # هنا تدخل أو تحدّث حالة الربط في جدول matches
    # مثال:
    cursor.execute("""
        INSERT INTO matches (client_id, captain_id, status)
        VALUES (%s, %s, %s)
        ON CONFLICT (client_id, captain_id) DO UPDATE SET status = EXCLUDED.status
    """, (client_id, captain_id, status))
    conn.commit()

    cur.close()def update_match(client_id, captain_id, status):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO matches (client_id, captain_id, status)
        VALUES (%s, %s, %s)
        ON CONFLICT (client_id, captain_id) DO UPDATE SET status = EXCLUDED.status
    """, (client_id, captain_id, status))
    conn.commit()
    cur.close()
    conn.close()

    conn.close()
