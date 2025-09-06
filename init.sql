-- ==========================================
-- قاعدة بيانات نظام طقطق - مبسطة
-- ==========================================

-- جدول المستخدمين
CREATE TABLE IF NOT EXISTS users (
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
    neighborhood2 TEXT,
    neighborhood3 TEXT,
    is_available BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- جدول الطلبات
CREATE TABLE IF NOT EXISTS matches (
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

-- جدول التقييمات
CREATE TABLE IF NOT EXISTS ratings (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id),
    client_id BIGINT REFERENCES users(user_id),
    captain_id BIGINT REFERENCES users(user_id),
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_rating UNIQUE (match_id, client_id)
);

-- فهارس أساسية للأداء
CREATE INDEX IF NOT EXISTS idx_available_captains ON users (role, is_available, city);
CREATE INDEX IF NOT EXISTS idx_active_matches ON matches (status, created_at);
CREATE INDEX IF NOT EXISTS idx_ratings_captain ON ratings (captain_id, rating);

-- دالة تحديث updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- تطبيق الدالة على جدول matches
CREATE TRIGGER update_matches_updated_at BEFORE UPDATE ON matches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
ALTER TABLE users RENAME COLUMN available TO is_available;
ALTER TABLE users ALTER COLUMN neighborhood2 SET DEFAULT '';
ALTER TABLE users ALTER COLUMN neighborhood3 SET DEFAULT '';
