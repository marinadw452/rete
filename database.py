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
    cursor = conn.cursor()
    
    # جدول المستخدمين
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        telegram_id BIGINT UNIQUE NOT NULL,
        role VARCHAR(10) NOT NULL CHECK (role IN ('client','captain')),
        subscription VARCHAR(10) NOT NULL CHECK (subscription IN ('daily','monthly')),
        full_name VARCHAR(100) NOT NULL,
        phone_number VARCHAR(20) NOT NULL,
        car_type VARCHAR(50),
        plate_number VARCHAR(20),
        capacity INTEGER,
        is_available BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # جدول الأحياء
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS neighborhoods (
        id SERIAL PRIMARY KEY,
        city VARCHAR(50) NOT NULL,
        neighborhood VARCHAR(100) NOT NULL
    );
    """)
    
    # جدول المطابقات
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS matches (
        id SERIAL PRIMARY KEY,
        client_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        captain_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        status VARCHAR(10) NOT NULL CHECK (status IN ('pending','accepted','rejected')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
