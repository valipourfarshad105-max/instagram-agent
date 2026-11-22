# 🚀 از اینجا شروع کنید

این راهنمای نصب سریع ایجنت اینستاگرام است. کل مسیر: **۵ تا ۳۰ دقیقه** بسته به اینکه
همین حالا شروع کنید یا بخواهید اتصال اینستاگرام را هم انجام دهید.

---

## 📦 داخل این بسته چیست؟

| مسیر | توضیح |
|---|---|
| `START-HERE.md` | همین فایل — راهنمای نصب |
| `README.md` | مستندات کامل پروژه + همهٔ دستورها |
| `docs/instagram-setup.md` | **راهنمای اتصال اینستاگرام (مهم‌ترین بخش)** |
| `docs/runbook.md` | نقشهٔ راه ۶ مرحله‌ای از صفر تا پست زنده + نگه‌داری ماهانه |
| `config.yaml` | تنظیمات برند، لحن، صدا، رنگ، ساعت‌های انتشار |
| `.env.example` | قالب کلیدها (کپی کنید و نامش را به `.env` تغییر دهید) |
| `agent/` | کد ایجنت (تولید محتوا، ویدیو، انتشار، داشبورد، زمان‌بند) |
| `assets/fonts/` | فونت فارسی وزیرمتن (۴ وزن) |
| `demo/` | یک ریلز نمونهٔ آمادهٔ تولیدشده + کپشن و سناریو |
| `Dockerfile` + `docker-compose.yml` | اجرا با داکر (اختیاری) |

---

## ⚡ نصب سریع (۳ دستور)

### ویندوز (PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m agent.cli init
python -m agent.cli generate
python -m agent.cli dashboard
```

### مک / لینوکس (ترمینال)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m agent.cli init
python -m agent.cli generate
python -m agent.cli dashboard
```

> اگر `python` روی مک پیدا نشد، از `python3` استفاده کنید. پیش‌نیاز سیستمی: **Python 3.10 یا بالاتر**
> (برای چک کردن: `python --version`).
>
> **ffmpeg** لازم است. اگر روی سیستم‌تان نیست، نصب سیستمی لازم نیست — پکیج
> `imageio-ffmpeg` که در `requirements.txt` هست، نسخهٔ آمادهٔ ffmpeg را خودش می‌آورد.
> اگر خواستید نسخهٔ سیستمی بگذارید: `brew install ffmpeg` (مک) یا
> `sudo apt install ffmpeg` (لینوکس).

بعد از اجرای `dashboard`، آدرس <http://localhost:8000> را در مرورگر باز کنید.

---

## ✅ گام‌به‌گام (پیشنهادی)

### گام ۱ — تست بدون هیچ کلیدی (۵ دقیقه)
دستورهای بالا را بزنید. در همین حالت هم ایجنت کار می‌کند: از قالب‌های آمادهٔ فارسی
متن می‌سازد، تصویر گرادیانی می‌کشد، گویندگی می‌کند و ریلز کامل می‌سازد.
**بدون پرداخت، بدون حساب، بدون کلید.**

اگر متن فارسی و صدا درست بود ⇒ زیرساخت سالم است ✅

### گام ۲ — کیفیت محتوا را بالا ببرید (۱۰ دقیقه)
1. کلید رایگان Gemini بگیرید: <https://aistudio.google.com/apikey> → **Create API key**
2. در فایل `.env` این خط را پر کنید:
   ```env
   GEMINI_API_KEY=کلید_شما
   ```
3. در `config.yaml` بخش `brand` را با برند خودتان پر کنید:
   ```yaml
   brand:
     name: "نام پیج شما"
     handle: "@your.page"
     niche: "حوزهٔ فعالیت شما"
     audience: "مخاطب هدف شما"
     tone: "لحن دلخواه شما"
     topics: ["موضوع ۱", "موضوع ۲", "موضوع ۳"]
   ```
4. تست: `python -m agent.cli generate --topic "موضوع دلخواه"`

### گام ۳ — اتصال اینستاگرام (۲۰ دقیقه)
راهنمای کامل و قدم‌به‌قدم در فایل **`docs/instagram-setup.md`** است. خلاصه:

1. اکانت اینستاگرام باید **Business یا Creator** باشد (اکانت شخصی نمی‌تواند منتشر کند).
2. در <https://developers.facebook.com/apps> یک اپ از نوع **Business** بسازید.
3. محصول **Instagram** را اضافه کنید و توکن با این دو دسترسی بگیرید:
   `instagram_business_basic` + `instagram_business_content_publish`
4. `IG_USER_ID` را بگیرید:
   ```bash
   curl "https://graph.instagram.com/v23.0/me?fields=id,username,account_type&access_token=توکن_شما"
   ```
5. در `.env` بگذارید و تست کنید:
   ```env
   IG_LOGIN=instagram
   IG_ACCESS_TOKEN=...
   IG_USER_ID=...
   ```
   ```bash
   python -m agent.cli ig-check
   ```

### گام ۴ — میزبانی ویدیو (۱۰ دقیقه، برای استفادهٔ واقعی)
اینستاگرام ویدیو را از یک **لینک عمومی** دانلود می‌کند. پیش‌فرض `uguu` است (بدون کلید،
ولی لینک موقت — فقط برای تست). برای پایداری، Cloudflare R2 را تنظیم کنید؛
دستورش در `docs/runbook.md` مرحلهٔ ۴.

### گام ۵ — اولین انتشار
```bash
python -m agent.cli list                          # شناسهٔ پست را بگیرید
python -m agent.cli approve <post-id>
python -m agent.cli publish <post-id>
```
یا همه از داشبورد: تأیید ✅ و بعد «انتشار فوری» 🚀

### گام ۶ — خودکارسازی
```bash
python -m agent.cli schedule     # زمان‌بند: طبق config.yaml پیش‌نویس می‌سازد
```
در `config.yaml`:
```yaml
publish:
  mode: approve                  # approve = شما تأیید می‌کنید | auto = کاملاً خودکار
  schedule: ["09:30", "19:00"]   # ساعت‌های اجرا (منطقهٔ زمانی تهران)
```
برای اجرای دائمی روی سرور (systemd یا داکر) بخش «اجرای دائمی» در `README.md`.

---

## 🧰 همهٔ دستورهای ایجنت

```bash
python -m agent.cli init              # ساخت پوشه‌ها و بررسی پیش‌نیازها
python -m agent.cli doctor            # چک‌لیست کامل کلیدها و اتصال‌ها
python -m agent.cli generate          # ساخت پست جدید (متن + تصویر + ویدیو)
python -m agent.cli generate --topic "موضوع" --publish
python -m agent.cli list              # فهرست پست‌ها
python -m agent.cli show <id>         # جزئیات یک پست
python -m agent.cli approve <id>      # تأیید
python -m agent.cli reject <id>       # رد
python -m agent.cli publish <id>      # انتشار در اینستاگرام
python -m agent.cli publish --all     # انتشار همهٔ تأییدشده‌ها
python -m agent.cli dashboard         # داشبورد تأیید در مرورگر
python -m agent.cli schedule          # زمان‌بند خودکار
python -m agent.cli ig-check          # تست اتصال اینستاگرام
python -m agent.cli publish-limit     # سهمیهٔ انتشار ۲۴ ساعت گذشته
python -m agent.cli refresh-token     # تمدید توکن ۶۰روزه
python -m agent.cli upload-test       # تست میزبان آپلود
python -m agent.cli rebuild-video <id># ساخت مجدد ویدیو
```
(به‌جای `python -m agent.cli` می‌توانید میان‌بر `python main.py` را هم بزنید.)

---

## 🔧 عیب‌یابی سریع

| مشکل | راه‌حل |
|---|---|
| `python: command not found` | از `python3` استفاده کنید یا Python را نصب کنید (۳.۱۰+) |
| `pip install` خطا داد | مطمئن شوید محیط مجازی فعال است (`.venv`)، بعد دوباره اجرا کنید |
| خطای ffmpeg | `pip install imageio-ffmpeg` (یا نسخهٔ سیستمی نصب کنید) |
| صدای فارسی ساخته نمی‌شود | `edge-tts` به اینترنت نیاز دارد؛ اتصال را چک کنید |
| متن فارسی جدا یا معکوس است | `python -c "from PIL import features; print(features.check('raqm'))"` — کد هر دو حالت را پوشش می‌دهد |
| خطای انتشار اینستاگرام | جدول خطاها در انتهای `docs/instagram-setup.md` |
| ویدیو منتشر نشد، خطای 9004 | هاست فایل مشکل داشت؛ آپلودر را به `s3`/R2 تغییر دهید |
| هر مشکل دیگری | `python -m agent.cli doctor` و لاگ‌های پوشهٔ `out/<post-id>/` |

---

## ⚠️ چهار نکتهٔ مهم

1. **اکانت شخصی نمی‌تواند خودکار پست بگذارد.** باید حرفه‌ای (Business/Creator) باشد —
   راهنمای تبدیل در `docs/instagram-setup.md` بخش ۰.
2. **هرگز رمز اینستاگرام را به هیچ برنامه‌ای ندهید.** این ایجنت فقط با «توکن رسمی متا»
   کار می‌کند که خودتان می‌سازید و هر زمان می‌توانید باطلش کنید.
3. **فایل `.env` را جایی آپلود نکنید** (توکن‌های شما آنجاست). در `.gitignore` هست.
4. **حالت پیش‌فرض «تأیید دستی» است** — هیچ‌چیز بدون نظر شما منتشر نمی‌شود. بعد از یکی دو
   هفته که به کیفیت خروجی‌ها مطمئن شدید، `mode: auto` را روشن کنید.

---

## 📖 ترتیب مطالعهٔ مستندات

1. همین فایل (نصب سریع) ✅
2. `README.md` → تصویر کلی، تنظیمات، اجرای دائمی
3. `docs/instagram-setup.md` → اتصال اینستاگرام (قبل از گام ۳ بخوانید)
4. `docs/runbook.md` → نقشهٔ راه کامل و نگه‌داری ماهانه

موفق باشید! 🎬
