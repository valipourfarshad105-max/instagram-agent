# ایجنت اینستاگرام — تصویر داکر (شامل ffmpeg و فونت فارسی وزیرمتن)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Tehran

# ffmpeg برای مونتاژ ویدیو و صداشناسی لازم است + فونت‌های پایه
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# پوشه‌های خروجی
RUN mkdir -p out data assets/music

EXPOSE 8000

# پیش‌فرض: زمان‌بند. برای داشبورد:  docker run ... python -m agent.cli dashboard
CMD ["python", "-m", "agent.cli", "schedule"]
