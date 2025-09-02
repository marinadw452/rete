# استخدام Python 3.11 كقاعدة
FROM python:3.11-slim

# تحديد مجلد العمل
WORKDIR /app

# نسخ ملف المتطلبات
COPY requirements.txt .

# تثبيت المتطلبات
RUN pip install --no-cache-dir -r requirements.txt

# نسخ الكود
COPY . .

# إنشاء مجلد اللوغات
RUN mkdir -p logs

# تحديد المتغيرات البيئية
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# تشغيل البوت
CMD ["python", "main.py"]
