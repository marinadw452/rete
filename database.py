import psycopg2
from psycopg2 import sql
from config import PG_DB, PG_USER, PG_PASSWORD, PG_HOST, PG_PORT

def init_db():
    # الاتصال بقاعدة البيانات باستخدام متغيرات البيئة
    conn = psycopg2.connect(
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        host=PG_HOST,
        port=PG_PORT
    )
    cur = conn.cursor()

    # ===== إنشاء جدول المستخدمين إذا لم يكن موجود =====
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
            agreement BOOLEAN DEFAULT FALSE
        );
    """)

    # ===== إضافة الأعمدة الناقصة إذا لم تكن موجودة =====
    columns_to_check = {
        "username": "TEXT"
    }

    for column, col_type in columns_to_check.items():
        cur.execute(sql.SQL("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS {} {};
        """).format(sql.Identifier(column), sql.SQL(col_type)))

    # ===== إنشاء جدول المطابقات إذا لم يكن موجود =====
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
