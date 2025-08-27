FROM python:3.11-slim

WORKDIR /app

# نسخ ملف الباكيجات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع
COPY . /app

# أمر التشغيل
CMD ["python", "main.py"]
