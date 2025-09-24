سن
-- قم بتشغيل هذا السكريپت في قاعدة البيانات الموجودة

-- إضافة الأعمدة الجديدة المطلوبة للجدول الموجود
-- إضافة حقول التقييم لجدول المستخدمين
ALTER TABLE users ADD COLUMN IF NOT EXISTS avg_rating DECIMAL(3,2) DEFAULT 0.00;
ALTER TABLE users ADD COLUMN IF NOT EXISTS total_ratings INTEGER DEFAULT 0;

-- إضافة قيود للتأكد من صحة البيانات
ALTER TABLE users ADD CONSTRAINT IF NOT EXISTS check_avg_rating 
    CHECK (avg_rating >= 0 AND avg_rating <= 5);
ALTER TABLE users ADD CONSTRAINT IF NOT EXISTS check_total_ratings 
    CHECK (total_ratings >= 0);

-- إنشاء جدول تنظيف الرسائل الجديد
CREATE TABLE IF NOT EXISTS message_cleanup (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    message_id INTEGER NOT NULL,
    message_type VARCHAR(50) DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    should_delete BOOLEAN DEFAULT TRUE,
    CONSTRAINT unique_message UNIQUE (chat_id, message_id)
);

-- إضافة حقل الملاحظات إلى جدول التقييمات الموجود
ALTER TABLE ratings ADD COLUMN IF NOT EXISTS comment TEXT;

-- تحديث القيود والفهارس
ALTER TABLE ratings DROP CONSTRAINT IF EXISTS unique_rating;
ALTER TABLE ratings DROP CONSTRAINT IF EXISTS unique_rating_per_match;
ALTER TABLE ratings ADD CONSTRAINT unique_rating_per_match UNIQUE (match_id);

-- إنشاء الفهارس المطلوبة لتحسين الأداء
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_city ON users(city);
CREATE INDEX IF NOT EXISTS idx_users_available ON users(is_available);
CREATE INDEX IF NOT EXISTS idx_users_rating ON users(avg_rating DESC);
CREATE INDEX IF NOT EXISTS idx_users_neighborhood ON users(city, neighborhood, neighborhood2, neighborhood3);

CREATE INDEX IF NOT EXISTS idx_matches_client ON matches(client_id);
CREATE INDEX IF NOT EXISTS idx_matches_captain ON matches(captain_id);
CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
CREATE INDEX IF NOT EXISTS idx_matches_created ON matches(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ratings_captain ON ratings(captain_id);
CREATE INDEX IF NOT EXISTS idx_ratings_client ON ratings(client_id);
CREATE INDEX IF NOT EXISTS idx_ratings_match ON ratings(match_id);
CREATE INDEX IF NOT EXISTS idx_ratings_created ON ratings(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_message_cleanup_chat ON message_cleanup(chat_id);
CREATE INDEX IF NOT EXISTS idx_message_cleanup_created ON message_cleanup(created_at);
CREATE INDEX IF NOT EXISTS idx_message_cleanup_should_delete ON message_cleanup(should_delete);

-- دالة لتحديث متوسط التقييم تلقائياً
CREATE OR REPLACE FUNCTION update_captain_rating()
RETURNS TRIGGER AS $$
BEGIN
    -- تحديث متوسط التقييم وعدد التقييمات للكابتن
    UPDATE users 
    SET 
        avg_rating = (
            SELECT COALESCE(AVG(rating)::DECIMAL(3,2), 0) 
            FROM ratings 
            WHERE captain_id = COALESCE(NEW.captain_id, OLD.captain_id)
        ),
        total_ratings = (
            SELECT COUNT(*) 
            FROM ratings 
            WHERE captain_id = COALESCE(NEW.captain_id, OLD.captain_id)
        )
    WHERE user_id = COALESCE(NEW.captain_id, OLD.captain_id);
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- حذف المحفز القديم إذا كان موجوداً وإنشاء الجديد
DROP TRIGGER IF EXISTS trigger_update_captain_rating ON ratings;
CREATE TRIGGER trigger_update_captain_rating
    AFTER INSERT OR UPDATE OR DELETE ON ratings
    FOR EACH ROW
    EXECUTE FUNCTION update_captain_rating();

-- دالة لتحديث وقت التحديث تلقائياً
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ربط دالة التحديث بجدول المطابقات
DROP TRIGGER IF EXISTS trigger_update_matches_modified ON matches;
CREATE TRIGGER trigger_update_matches_modified
    BEFORE UPDATE ON matches
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();

-- دالة للبحث عن الكباتن المتاحين مع التقييمات (محسنة)
CREATE OR REPLACE FUNCTION find_available_captains_in_area(
    search_city TEXT,
    search_neighborhood TEXT
)
RETURNS TABLE(
    user_id BIGINT,
    username TEXT,
    full_name TEXT,
    phone TEXT,
    car_model TEXT,
    car_plate TEXT,
    city TEXT,
    neighborhood TEXT,
    neighborhood2 TEXT,
    neighborhood3 TEXT,
    is_available BOOLEAN,
    avg_rating DECIMAL,
    total_ratings INTEGER,
    created_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        u.user_id,
        u.username,
        u.full_name,
        u.phone,
        u.car_model,
        u.car_plate,
        u.city,
        u.neighborhood,
        u.neighborhood2,
        u.neighborhood3,
        u.is_available,
        u.avg_rating,
        u.total_ratings,
        u.created_at
    FROM users u
    WHERE u.role = 'captain' 
        AND u.is_available = TRUE 
        AND u.city = search_city
        AND (search_neighborhood = u.neighborhood 
             OR search_neighborhood = u.neighborhood2 
             OR search_neighborhood = u.neighborhood3)
    ORDER BY u.avg_rating DESC, u.created_at ASC;
END;
$$ LANGUAGE plpgsql;

-- تحديث التقييمات الحالية للكباتن الموجودين
UPDATE users 
SET 
    avg_rating = COALESCE((
        SELECT AVG(rating)::DECIMAL(3,2) 
        FROM ratings 
        WHERE captain_id = users.user_id
    ), 0),
    total_ratings = COALESCE((
        SELECT COUNT(*) 
        FROM ratings 
        WHERE captain_id = users.user_id
    ), 0)
WHERE role = 'captain';

-- view محدث لإحصائيات الكباتن
DROP VIEW IF EXISTS captain_stats;
CREATE VIEW captain_stats AS
SELECT 
    u.user_id,
    u.full_name,
    u.city,
    u.neighborhood,
    u.neighborhood2,
    u.neighborhood3,
    u.car_model,
    u.car_plate,
    u.avg_rating,
    u.total_ratings,
    u.is_available,
    COUNT(m.id) as total_trips,
    COUNT(CASE WHEN m.status = 'completed' THEN 1 END) as completed_trips,
    COUNT(CASE WHEN m.status = 'in_progress' THEN 1 END) as active_trips
FROM users u
LEFT JOIN matches m ON u.user_id = m.captain_id
WHERE u.role = 'captain'
GROUP BY u.user_id, u.full_name, u.city, u.neighborhood, u.neighborhood2, u.neighborhood3, 
         u.car_model, u.car_plate, u.avg_rating, u.total_ratings, u.is_available;

-- view لإحصائيات العملاء
DROP VIEW IF EXISTS client_stats;
CREATE VIEW client_stats AS
SELECT 
    u.user_id,
    u.full_name,
    u.city,
    u.neighborhood,
    COUNT(m.id) as total_requests,
    COUNT(CASE WHEN m.status = 'completed' THEN 1 END) as completed_trips,
    COUNT(CASE WHEN m.status = 'pending' THEN 1 END) as pending_requests
FROM users u
LEFT JOIN matches m ON u.user_id = m.client_id
WHERE u.role = 'client'
GROUP BY u.user_id, u.full_name, u.city, u.neighborhood;

-- view للتقييمات التفصيلية
DROP VIEW IF EXISTS detailed_ratings;
CREATE VIEW detailed_ratings AS
SELECT 
    r.id,
    r.rating,
    r.comment,
    r.created_at,
    c.full_name as client_name,
    cap.full_name as captain_name,
    cap.car_model,
    cap.car_plate,
    m.destination
FROM ratings r
JOIN users c ON r.client_id = c.user_id
JOIN users cap ON r.captain_id = cap.user_id
JOIN matches m ON r.match_id = m.id
ORDER BY r.created_at DESC;

-- التحقق من التحديثات
SELECT 'تم تحديث قاعدة البيانات بنجاح!' as status;

-- عرض إحصائيات سريعة بعد التحديث
SELECT 
    'إحصائيات قاعدة البيانات:' as info,
    (SELECT COUNT(*) FROM users WHERE role = 'client') as total_clients,
    (SELECT COUNT(*) FROM users WHERE role = 'captain') as total_captains,
    (SELECT COUNT(*) FROM matches) as total_matches,
    (SELECT COUNT(*) FROM ratings) as total_ratings,
    (SELECT COUNT(*) FROM message_cleanup) as cleanup_messages;
