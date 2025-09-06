# استخدام Python 3.11 كقاعدة
FROM python:3.11-slim

# تحديد مجلد العمل
WORKDIR /app

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
