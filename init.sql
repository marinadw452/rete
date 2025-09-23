-- إضافة حقل الملاحظات إلى جدول التقييمات الموجود
ALTER TABLE ratings ADD COLUMN IF NOT EXISTS notes TEXT;

-- إضافة تعليق على الحقل الجديد
COMMENT ON COLUMN ratings.notes IS 'ملاحظات خاصة من العميل';

-- تحديث القيد الفريد للتأكد من عدم تكرار التقييمات
ALTER TABLE ratings DROP CONSTRAINT IF EXISTS unique_rating;
ALTER TABLE ratings ADD CONSTRAINT unique_rating UNIQUE (match_id, client_id);

-- إضافة فهرس للبحث السريع في التقييمات
CREATE INDEX IF NOT EXISTS idx_ratings_match ON ratings (match_id);

-- إنشاء view محدث لإحصائيات الكباتن مع متوسط التقييمات
CREATE OR REPLACE VIEW captain_stats AS
SELECT 
    u.user_id,
    u.full_name,
    u.car_model,
    u.car_plate,
    u.is_available,
    COUNT(m.id) as total_rides,
    COUNT(CASE WHEN m.status = 'completed' THEN 1 END) as completed_rides,
    COUNT(CASE WHEN m.status = 'in_progress' THEN 1 END) as active_rides,
    COALESCE(ROUND(AVG(r.rating), 1), 0) as average_rating,
    COUNT(r.id) as total_ratings
FROM users u
LEFT JOIN matches m ON u.user_id = m.captain_id
LEFT JOIN ratings r ON m.id = r.match_id
WHERE u.role = 'captain'
GROUP BY u.user_id, u.full_name, u.car_model, u.car_plate, u.is_available;

-- التأكد من وجود الفهارس المطلوبة لتحسين الأداء
CREATE INDEX IF NOT EXISTS idx_available_captains ON users (role, is_available, city);
CREATE INDEX IF NOT EXISTS idx_neighborhood_search ON users (neighborhood, neighborhood2, neighborhood3);
CREATE INDEX IF NOT EXISTS idx_active_matches ON matches (status, created_at);
CREATE INDEX IF NOT EXISTS idx_client_matches ON matches (client_id, status);
CREATE INDEX IF NOT EXISTS idx_captain_matches ON matches (captain_id, status);
CREATE INDEX IF NOT EXISTS idx_ratings_captain ON ratings (captain_id, rating);

-- إنشاء دالة للبحث عن الكباتن المتاحين مع التقييمات
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
    average_rating NUMERIC,
    total_ratings BIGINT
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
        COALESCE(ROUND(AVG(r.rating), 1), 0) as average_rating,
        COUNT(r.id) as total_ratings
    FROM users u
    LEFT JOIN matches m ON u.user_id = m.captain_id AND m.status = 'completed'
    LEFT JOIN ratings r ON m.id = r.match_id
    WHERE u.role = 'captain' 
        AND u.is_available = TRUE 
        AND u.city = search_city
        AND (search_neighborhood = u.neighborhood 
             OR search_neighborhood = u.neighborhood2 
             OR search_neighborhood = u.neighborhood3)
    GROUP BY u.user_id, u.full_name, u.car_model, u.car_plate, u.phone, 
             u.neighborhood, u.neighborhood2, u.neighborhood3
    ORDER BY average_rating DESC, u.created_at ASC;
END;
$$ LANGUAGE plpgsql;

-- التأكد من وجود المحفز لتحديث updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_matches_updated_at ON matches;
CREATE TRIGGER update_matches_updated_at 
    BEFORE UPDATE ON matches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- استعلام للتحقق من البيانات الحالية
SELECT 'Current ratings structure:' as info;
SELECT column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_name = 'ratings'
ORDER BY ordinal_position;

-- إحصائيات سريعة
SELECT 
    'Database Statistics:' as info,
    (SELECT COUNT(*) FROM users WHERE role = 'client') as total_clients,
    (SELECT COUNT(*) FROM users WHERE role = 'captain') as total_captains,
    (SELECT COUNT(*) FROM matches) as total_matches,
    (SELECT COUNT(*) FROM ratings) as total_ratings;
