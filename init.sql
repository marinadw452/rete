-- إنشاء امتداد للوقت
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==========================================
-- جدول المستخدمين
-- ==========================================
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,                    -- معرف تليجرام
    username TEXT,                                 -- يوزرنيم تليجرام
    role VARCHAR(10) NOT NULL CHECK (role IN ('client', 'captain')), -- الدور
    subscription VARCHAR(20) CHECK (subscription IN ('daily', 'monthly')), -- نوع الاشتراك
    full_name TEXT NOT NULL,                       -- الاسم الكامل
    phone TEXT NOT NULL,                           -- رقم الجوال
    
    -- بيانات الكابتن (اختيارية للعملاء)
    car_model TEXT,                                -- موديل السيارة
    car_plate TEXT,                                -- رقم اللوحة
    
    -- بيانات عامة
    agreement BOOLEAN DEFAULT FALSE,               -- الموافقة على الشروط
    city TEXT NOT NULL,                           -- المدينة
    neighborhood TEXT NOT NULL,                   -- الحي الأساسي
    neighborhood2 TEXT,                           -- الحي الثاني (للكباتن)
    neighborhood3 TEXT,                           -- الحي الثالث (للكباتن)
    is_available BOOLEAN DEFAULT TRUE,            -- متاح/غير متاح
    
    -- تواريخ
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- جدول المطابقات/الطلبات
-- ==========================================
CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,                        -- معرف الطلب
    client_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, -- معرف العميل
    captain_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, -- معرف الكابتن
    destination TEXT NOT NULL,                    -- الوجهة المطلوبة
    
    -- حالة الطلب
    status VARCHAR(20) DEFAULT 'pending' CHECK (
        status IN ('pending', 'in_progress', 'rejected', 'cancelled', 'completed')
    ),
    
    -- تواريخ
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- منع الطلبات المكررة النشطة
    CONSTRAINT unique_active_match UNIQUE (client_id, captain_id)
);

-- ==========================================
-- جدول التقييمات
-- ==========================================
CREATE TABLE IF NOT EXISTS ratings (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id) ON DELETE CASCADE,
    client_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE, -- من قيّم
    captain_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE, -- من تم تقييمه
    rating INTEGER CHECK (rating >= 1 AND rating <= 5), -- التقييم من 1 إلى 5
    comment TEXT,                                 -- تعليق
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- منع التقييم المكرر لنفس الرحلة
    CONSTRAINT unique_rating UNIQUE (match_id, client_id)
);

-- ==========================================
-- جدول سجل العمليات (لوق)
-- ==========================================
CREATE TABLE IF NOT EXISTS activity_logs (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,                  -- نوع العملية
    details JSONB,                                -- تفاصيل العملية
    ip_address INET,                              -- عنوان IP (اختياري)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- الفهارس لتحسين الأداء
-- ==========================================

-- فهرس البحث عن الكباتن المتاحين
CREATE INDEX IF NOT EXISTS idx_available_captains ON users (role, is_available, city)
WHERE role = 'captain' AND is_available = TRUE;

-- فهرس الطلبات النشطة
CREATE INDEX IF NOT EXISTS idx_active_matches ON matches (status, created_at)
WHERE status IN ('pending', 'in_progress');

-- فهرس البحث بالمدينة والأحياء
CREATE INDEX IF NOT EXISTS idx_users_location ON users (city, neighborhood, neighborhood2, neighborhood3);

-- فهرس المطابقات حسب التاريخ
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches (created_at DESC);

-- فهرس التقييمات
CREATE INDEX IF NOT EXISTS idx_ratings_captain ON ratings (captain_id, rating);

-- فهرس الوجهات
CREATE INDEX IF NOT EXISTS idx_destinations ON matches (destination);

-- ==========================================
-- الدوال المساعدة (Functions)
-- ==========================================

-- دالة تحديث الـ updated_at تلقائياً
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$ language 'plpgsql';

-- تطبيق الدالة على الجداول
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();-- ==========================================
-- سكريبت إنشاء قاعدة بيانات نظام طقطق
-- PostgreSQL Database Schema
-- ==========================================

-- إنشاء امتداد للوقت
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==========================================
-- جدول المستخدمين
-- ==========================================
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,                    -- معرف تليجرام
    username TEXT,                                 -- يوزرنيم تليجرام
    role VARCHAR(10) NOT NULL CHECK (role IN ('client', 'captain')), -- الدور
    subscription VARCHAR(20) CHECK (subscription IN ('daily', 'monthly')), -- نوع الاشتراك
    full_name TEXT NOT NULL,                       -- الاسم الكامل
    phone TEXT NOT NULL,                           -- رقم الجوال
    
    -- بيانات الكابتن (اختيارية للعملاء)
    car_model TEXT,                                -- موديل السيارة
    car_plate TEXT,                                -- رقم اللوحة
    seats INTEGER CHECK (seats >= 1 AND seats <= 8), -- عدد المقاعد
    
    -- بيانات عامة
    agreement BOOLEAN DEFAULT FALSE,               -- الموافقة على الشروط
    city TEXT NOT NULL,                           -- المدينة
    neighborhood TEXT NOT NULL,                   -- الحي
    is_available BOOLEAN DEFAULT TRUE,            -- متاح/غير متاح
    
    -- تواريخ
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- جدول المطابقات/الطلبات
-- ==========================================
CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,                        -- معرف الطلب
    client_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, -- معرف العميل
    captain_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, -- معرف الكابتن
    
    -- حالة الطلب
    status VARCHAR(20) DEFAULT 'pending' CHECK (
        status IN ('pending', 'captain_accepted', 'rejected', 'cancelled', 'completed')
    ),
    
    -- تأكيد العميل النهائي
    client_confirmed BOOLEAN DEFAULT FALSE,
    
    -- تفاصيل إضافية
    pickup_location TEXT,                         -- نقطة الانطلاق
    destination TEXT,                             -- الوجهة
    notes TEXT,                                   -- ملاحظات
    
    -- تواريخ
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- منع الطلبات المكررة النشطة
    CONSTRAINT unique_active_match UNIQUE (client_id, captain_id)
);

-- ==========================================
-- جدول تقييمات الرحلات (اختياري)
-- ==========================================
CREATE TABLE IF NOT EXISTS ratings (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id) ON DELETE CASCADE,
    rated_by BIGINT REFERENCES users(user_id) ON DELETE CASCADE, -- من قيّم
    rated_user BIGINT REFERENCES users(user_id) ON DELETE CASCADE, -- من تم تقييمه
    rating INTEGER CHECK (rating >= 1 AND rating <= 5), -- التقييم من 1 إلى 5
    comment TEXT,                                 -- تعليق
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- منع التقييم المكرر لنفس الرحلة
    CONSTRAINT unique_rating UNIQUE (match_id, rated_by)
);

-- ==========================================
-- جدول سجل العمليات (لوق)
-- ==========================================
CREATE TABLE IF NOT EXISTS activity_logs (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,                  -- نوع العملية
    details JSONB,                                -- تفاصيل العملية
    ip_address INET,                              -- عنوان IP (اختياري)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- الفهارس لتحسين الأداء
-- ==========================================

-- فهرس البحث عن الكباتن المتاحين
CREATE INDEX IF NOT EXISTS idx_available_captains ON users (role, is_available, city, neighborhood)
WHERE role = 'captain' AND is_available = TRUE;

-- فهرس الطلبات النشطة
CREATE INDEX IF NOT EXISTS idx_active_matches ON matches (status, created_at)
WHERE status IN ('pending', 'captain_accepted');

-- فهرس البحث بالمدينة والحي
CREATE INDEX IF NOT EXISTS idx_users_location ON users (city, neighborhood);

-- فهرس المطابقات حسب التاريخ
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches (created_at DESC);

-- فهرس التقييمات
CREATE INDEX IF NOT EXISTS idx_ratings_user ON ratings (rated_user, rating);

-- ==========================================
-- الدوال المساعدة (Functions)
-- ==========================================

-- دالة تحديث الـ updated_at تلقائياً
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$ language 'plpgsql';

-- تطبيق الدالة على الجداول
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_matches_updated_at ON matches;
CREATE TRIGGER update_matches_updated_at BEFORE UPDATE ON matches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ==========================================
-- دالة البحث عن الكباتن المتاحين
-- ==========================================
CREATE OR REPLACE FUNCTION find_available_captains(
    search_city TEXT,
    search_neighborhood TEXT
)
RETURNS TABLE (
    user_id BIGINT,
    username TEXT,
    full_name TEXT,
    phone TEXT,
    car_model TEXT,
    car_plate TEXT,
    seats INTEGER,
    created_at TIMESTAMP
) AS $
BEGIN
    RETURN QUERY
    SELECT 
        u.user_id,
        u.username,
        u.full_name,
        u.phone,
        u.car_model,
        u.car_plate,
        u.seats,
        u.created_at
    FROM users u
    WHERE u.role = 'captain'
      AND u.is_available = TRUE
      AND u.city = search_city
      AND u.neighborhood = search_neighborhood
    ORDER BY u.created_at ASC;
END;
$ LANGUAGE plpgsql;

-- ==========================================
-- دالة إحصائيات النظام
-- ==========================================
CREATE OR REPLACE FUNCTION get_system_stats()
RETURNS TABLE (
    total_users BIGINT,
    total_clients BIGINT,
    total_captains BIGINT,
    available_captains BIGINT,
    total_matches BIGINT,
    completed_matches BIGINT,
    pending_matches BIGINT
) AS $
BEGIN
    RETURN QUERY
    SELECT 
        (SELECT COUNT(*) FROM users)::BIGINT as total_users,
        (SELECT COUNT(*) FROM users WHERE role = 'client')::BIGINT as total_clients,
        (SELECT COUNT(*) FROM users WHERE role = 'captain')::BIGINT as total_captains,
        (SELECT COUNT(*) FROM users WHERE role = 'captain' AND is_available = TRUE)::BIGINT as available_captains,
        (SELECT COUNT(*) FROM matches)::BIGINT as total_matches,
        (SELECT COUNT(*) FROM matches WHERE status = 'completed')::BIGINT as completed_matches,
        (SELECT COUNT(*) FROM matches WHERE status = 'pending')::BIGINT as pending_matches;
END;
$ LANGUAGE plpgsql;

-- ==========================================
-- بيانات تجريبية (اختيارية)
-- ==========================================

-- إدراج بيانات كباتن تجريبية
INSERT INTO users (user_id, username, role, subscription, full_name, phone, car_model, car_plate, seats, agreement, city, neighborhood) VALUES
(1001, 'captain1', 'captain', 'monthly', 'أحمد محمد', '0501234567', 'كامري 2020', 'أ ب ج 1234', 4, TRUE, 'الرياض', 'الملز'),
(1002, 'captain2', 'captain', 'daily', 'سعد عبدالله', '0509876543', 'أكورد 2019', 'د هـ و 5678', 3, TRUE, 'جدة', 'الروضة'),
(1003, 'captain3', 'captain', 'monthly', 'خالد الحربي', '0507777777', 'التيما 2021', 'ز ح ط 9999', 4, TRUE, 'الرياض', 'العليا')
ON CONFLICT (user_id) DO NOTHING;

-- إدراج بيانات عملاء تجريبية
INSERT INTO users (user_id, username, role, subscription, full_name, phone, agreement, city, neighborhood) VALUES
(2001, 'client1', 'client', 'daily', 'فاطمة أحمد', '0551111111', TRUE, 'الرياض', 'الملز'),
(2002, 'client2', 'client', 'monthly', 'محمد السعيد', '0552222222', TRUE, 'جدة', 'الروضة')
ON CONFLICT (user_id) DO NOTHING;

-- ==========================================
-- استعلامات مفيدة للمراقبة
-- ==========================================

-- عرض جميع الكباتن المتاحين
-- SELECT * FROM find_available_captains('الرياض', 'الملز');

-- عرض إحصائيات النظام
-- SELECT * FROM get_system_stats();

-- عرض الطلبات المُعلقة
-- SELECT m.*, 
--        c.full_name as client_name, 
--        cap.full_name as captain_name
-- FROM matches m
-- JOIN users c ON m.client_id = c.user_id
-- JOIN users cap ON m.captain_id = cap.user_id
-- WHERE m.status = 'pending'
-- ORDER BY m.created_at DESC;

-- عرض آخر النشاطات
-- SELECT u.full_name, u.role, u.city, u.neighborhood, u.created_at
-- FROM users u
-- ORDER BY u.created_at DESC
-- LIMIT 10;
