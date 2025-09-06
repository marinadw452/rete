-- ==========================================
-- قاعدة بيانات نظام طقطق - نسخة نظيفة
-- ==========================================

-- حذف الجداول إذا كانت موجودة
DROP TABLE IF EXISTS ratings CASCADE;
DROP TABLE IF EXISTS matches CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- ================= جدول المستخدمين =================
CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    role VARCHAR(10) NOT NULL CHECK (role IN ('client', 'captain')),
    subscription VARCHAR(20),
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    car_model TEXT,
    car_plate TEXT,
    agreement BOOLEAN DEFAULT FALSE,
    city TEXT NOT NULL,
    neighborhood TEXT NOT NULL,
    neighborhood2 TEXT DEFAULT '',
    neighborhood3 TEXT DEFAULT '',
    is_available BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- فهارس الأداء للمستخدمين
CREATE INDEX idx_available_captains ON users (role, is_available, city);

-- ================= جدول الطلبات =================
CREATE TABLE matches (
    id SERIAL PRIMARY KEY,
    client_id BIGINT REFERENCES users(user_id),
    captain_id BIGINT REFERENCES users(user_id),
    destination TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' CHECK (
        status IN ('pending', 'in_progress', 'rejected', 'cancelled', 'completed')
    ),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_pending_match UNIQUE (client_id, captain_id)
);

-- فهارس الأداء للطلبات
CREATE INDEX idx_active_matches ON matches (status, created_at);

-- دالة لتحديث updated_at تلقائيًا
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- تطبيق الدالة على جدول الطلبات
CREATE TRIGGER update_matches_updated_at BEFORE UPDATE ON matches
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ================= جدول التقييمات =================
CREATE TABLE ratings (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id),
    client_id BIGINT REFERENCES users(user_id),
    captain_id BIGINT REFERENCES users(user_id),
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_rating UNIQUE (match_id, client_id)
);

-- فهارس الأداء للتقييمات
CREATE INDEX idx_ratings_captain ON ratings (captain_id, rating);
