-- ==========================================
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
