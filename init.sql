DROP TABLE IF EXISTS ratings CASCADE;
DROP TABLE IF EXISTS matches CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- حذف الدوال الموجودة
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;

-- إنشاء جدول المستخدمين
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
    neighborhood2 TEXT,
    neighborhood3 TEXT,
    is_available BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- إنشاء جدول المطابقات
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

-- إنشاء جدول التقييمات مع حقل الملاحظات الجديد
CREATE TABLE ratings (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id),
    client_id BIGINT REFERENCES users(user_id),
    captain_id BIGINT REFERENCES users(user_id),
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_rating UNIQUE (match_id, client_id)
);

-- إنشاء الفهارس لتحسين الأداء
CREATE INDEX idx_available_captains ON users (role, is_available, city);
CREATE INDEX idx_neighborhood_search ON users (neighborhood, neighborhood2, neighborhood3);
CREATE INDEX idx_active_matches ON matches (status, created_at);
CREATE INDEX idx_client_matches ON matches (client_id, status);
CREATE INDEX idx_captain_matches ON matches (captain_id, status);
CREATE INDEX idx_ratings_captain ON ratings (captain_id, rating);
CREATE INDEX idx_ratings_match ON ratings (match_id);

-- إنشاء دالة تحديث updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- إنشاء المحفز لتحديث updated_at تلقائياً
CREATE TRIGGER update_matches_updated_at 
    BEFORE UPDATE ON matches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- إدراج بيانات تجريبية (اختيارية)
INSERT INTO users (user_id, username, role, full_name, phone, city, neighborhood, agreement) VALUES
(123456789, 'test_client', 'client', 'أحمد محمد', '0501234567', 'الرياض', 'الملك فهد', TRUE),
(987654321, 'test_captain', 'captain', 'محمد أحمد', '0509876543', 'الرياض', 'الملك فهد', TRUE);

-- تحديث بيانات الكابتن التجريبي
UPDATE users SET 
    car_model = 'كامري 2020',
    car_plate = 'أ ب ج 1234',
    neighborhood2 = 'العليا',
    neighborhood3 = 'الملك عبدالله'
WHERE user_id = 987654321;

-- إنشاء view لإحصائيات الكباتن
CREATE VIEW captain_stats AS
SELECT 
    u.user_id,
    u.full_name,
    u.car_model,
    u.car_plate,
    u.is_available,
    COUNT(m.id) as total_rides,
    COUNT(CASE WHEN m.status = 'completed' THEN 1 END) as completed_rides,
    COUNT(CASE WHEN m.status = 'in_progress' THEN 1 END) as active_rides,
    COALESCE(AVG(r.rating), 0) as average_rating,
    COUNT(r.id) as total_ratings
FROM users u
LEFT JOIN matches m ON u.user_id = m.captain_id
LEFT JOIN ratings r ON m.id = r.match_id
WHERE u.role = 'captain'
GROUP BY u.user_id, u.full_name, u.car_model, u.car_plate, u.is_available;

-- إنشاء view لإحصائيات العملاء
CREATE VIEW client_stats AS
SELECT 
    u.user_id,
    u.full_name,
    u.city,
    u.neighborhood,
    COUNT(m.id) as total_requests,
    COUNT(CASE WHEN m.status = 'completed' THEN 1 END) as completed_trips,
    COUNT(CASE WHEN m.status = 'pending' THEN 1 END) as pending_requests,
    COUNT(CASE WHEN m.status = 'cancelled' THEN 1 END) as cancelled_requests
FROM users u
LEFT JOIN matches m ON u.user_id = m.client_id
WHERE u.role = 'client'
GROUP BY u.user_id, u.full_name, u.city, u.neighborhood;

-- إنشاء دالة للبحث عن الكباتن المتاحين
CREATE OR REPLACE FUNCTION find_available_captains_in_area(
    search_city TEXT,
    search_neighborhood TEXT
)
RETURNS TABLE(
    user_id BIGINT,
    full_name TEXT,
    car_model TEXT,
    car_plate TEXT,
    phone TEXT,
    neighborhood TEXT,
    neighborhood2 TEXT,
    neighborhood3 TEXT,
    average_rating NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        u.user_id,
        u.full_name,
        u.car_model,
        u.car_plate,
        u.phone,
        u.neighborhood,
        u.neighborhood2,
        u.neighborhood3,
        COALESCE(AVG(r.rating), 0) as average_rating
    FROM users u
    LEFT JOIN matches m ON u.user_id = m.captain_id
    LEFT JOIN ratings r ON m.id = r.match_id
    WHERE u.role = 'captain' 
        AND u.is_available = TRUE 
        AND u.city = search_city
        AND (search_neighborhood = u.neighborhood 
             OR search_neighborhood = u.neighborhood2 
             OR search_neighborhood = u.neighborhood3)
    GROUP BY u.user_id, u.full_name, u.car_model, u.car_plate, u.phone, u.neighborhood, u.neighborhood2, u.neighborhood3
    ORDER BY u.created_at ASC;
END;
$$ LANGUAGE plpgsql;

-- إضافة تعليقات على الجداول
COMMENT ON TABLE users IS 'جدول المستخدمين - العملاء والكباتن';
COMMENT ON TABLE matches IS 'جدول المطابقات والطلبات';
COMMENT ON TABLE ratings IS 'جدول التقييمات مع التعليقات والملاحظات';

COMMENT ON COLUMN ratings.comment IS 'تعليق العميل على الخدمة';
COMMENT ON COLUMN ratings.notes IS 'ملاحظات خاصة من العميل';
COMMENT ON COLUMN matches.destination IS 'الوجهة المطلوبة للرحلة';
COMMENT ON COLUMN users.is_available IS 'حالة توفر الكابتن';

-- منح الصلاحيات (قم بتعديل اسم المستخدم حسب الحاجة)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_app_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO your_app_user;
