
FROM python:3.11-slim

# تحديد مجلد العمل
WORKDIR /app

# تثبيت المتطلبات الأساسية
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# نسخ ملف المتطلبات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ جميع ملفات البوت
COPY . .

# تحديد متغيرات البيئة
ENV PYTHONUNBUFFERED=1

# تشغيل البوت المحسن
CMD ["python", "improved_bot.py"]
