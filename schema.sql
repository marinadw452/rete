-- إنشاء جدول المستخدمين إذا لم يكن موجود
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

-- إنشاء جدول المطابقات إذا لم يكن موجود
CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,
    client_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    captain_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'pending',
    CONSTRAINT unique_match UNIQUE (client_id, captain_id)
);
