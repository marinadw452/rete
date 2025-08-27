import psycopg2
import psycopg2.extras
from config import PG_DB, PG_USER, PG_PASSWORD, PG_HOST, PG_PORT

# ================== اتصال بالقاعدة ==================
def get_conn():
    return psycopg2.connect(
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        host=PG_HOST,
        port=PG_PORT,
        cursor_factory=psycopg2.extras.RealDictCursor
    )

# ================== إنشاء الجداول لو ما هي موجودة ==================
def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS matches (
        id SERIAL PRIMARY KEY,
        client_id BIGINT NOT NULL,
        captain_id BIGINT NOT NULL,
        status VARCHAR(20) NOT NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (client_id, captain_id)
    );
    """)

    conn.commit()
    cur.close()
    conn.close()

# ================== تحديث أو إضافة مطابقة ==================
def update_match(client_id: int, captain_id: int, status: str):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO matches (client_id, captain_id, status)
        VALUES (%s, %s, %s)
        ON CONFLICT (client_id, captain_id)
        DO UPDATE SET status = EXCLUDED.status;
    """, (client_id, captain_id, status))

    conn.commit()
    cur.close()
    conn.close()
