-- جدول المستخدمين
CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,
    role VARCHAR(10),
    subscription VARCHAR(10),
    full_name TEXT,
    phone TEXT,
    car_model TEXT,
    car_plate TEXT,
    seats INT,
    city TEXT,
    neighborhood TEXT,
    is_available BOOLEAN DEFAULT TRUE,
    agreed BOOLEAN DEFAULT FALSE
);

-- جدول المطابقات
CREATE TABLE matches (
    id SERIAL PRIMARY KEY,
    client_id BIGINT REFERENCES users(user_id),
    captain_id BIGINT REFERENCES users(user_id),
    status VARCHAR(10) DEFAULT 'pending'
);
