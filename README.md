# 🤖 ایجنت اینستاگرام — ساخت و انتشار خودکار ریلز فارسی

یک ایجنت کامل که خودش **ایده می‌گیرد، سناریو و کپشن فارسی می‌نویسد، تصویر می‌سازد،
گویندگی می‌کند، ویدیوی ۹:۱۶ می‌سازد و در اینستاگرام منتشر می‌کند** — از طریق
Instagram Graph API رسمی متا (بدون رمز شما، بدون ابزار غیرمجاز).

```
ایده ──► متن و سناریو ──► تصویرهای صحنه ──► گویندگی فارسی ──► مونتاژ ریلز ──► [تأیید شما] ──► انتشار
```

---

## ✅ چه چیزی همین الان آماده است

- **حالت بدون کلید (offline)**: با قالب‌های آمادهٔ فارسی کار می‌کند؛ برای تست کل زنجیره.
- **حالت هوش مصنوعی**: با `GEMINI_API_KEY` یا `OPENAI_API_KEY` متن و تصویر اختصاصی می‌سازد.
- **گویندگی فارسی رایگان**: دو صدای `fa-IR-FaridNeural` (مرد) و `fa-IR-DilaraNeural` (زن).
- **داشبورد تأیید**: ویدیو را می‌بینید، کپشن را ویرایش می‌کنید، تأیید/رد/انتشار فوری.
- **دو حالت کاری**: `approve` (تأیید دستی — پیش‌فرض) و `auto` (کاملاً خودکار).
- **زمان‌بند**: در ساعت‌های دلخواه شما هر روز اجرا می‌شود (منطقهٔ زمانی تهران).
- **اعلان تلگرام**: پیش‌نویس جدید + لینک داشبورد (اختیاری).
- **۵ گزینهٔ میزبانی ویدیو**: `uguu`/`litterbox` (بدون کلید، موقت) و `s3`/R2 (پیشنهاد واقعی)، `local`.
- **ضد خطا**: اگر مدل هوش مصنوعی جواب نداد، خودش به قالب آفلاین برمی‌گردد؛ اگر تصویر نیامد،
  پس‌زمینهٔ گرادیانی می‌سازد؛ اگر اینستاگرام خطا داد، تا ۳ بار دوباره تلاش می‌کند.

---

## 🚀 راه‌اندازی در ۴ قدم

### ۱) نصب پیش‌نیازها
```bash
cd instagram-agent
python -m venv .venv && source .venv/bin/activate     # ویندوز: .venv\Scripts\activate
pip install -r requirements.txt
```

**ffmpeg** لازم است. یکی از این راه‌ها:
```bash
sudo apt install ffmpeg      # اوبونتو/دبیان
brew install ffmpeg          # مک
# یا بدون نصب سیستمی: pip install imageio-ffmpeg  (همین حالا در requirements هست)
```

### ۲) پیکربندی
```bash
cp .env.example .env      # سپس .env را باز کنید و کلیدها را بگذارید
```
حداقلِ لازم برای شروع آزمایشی: **هیچ کلیدی!** (حالت آفلاین + آپلودر uguu).
برای استفادهٔ واقعی: `GEMINI_API_KEY` + توکن اینستاگرام (راهنما: [`docs/instagram-setup.md`](docs/instagram-setup.md)).

فایل [`config.yaml`](config.yaml) را باز کنید و برند خودتان را تنظیم کنید:
```yaml
brand:
  name: "نام پیج شما"
  handle: "@your.page"
  niche: "حوزهٔ فعالیت شما"
  audience: "مخاطب هدف شما"
  tone: "لحن دلخواه"
  topics: ["موضوع ۱", "موضوع ۲", ...]
```

### ۳) بررسی سلامت
```bash
python -m agent.cli init       # پوشه‌ها، ffmpeg، فونت فارسی
python -m agent.cli doctor     # چک‌لیست کامل کلیدها و اتصال‌ها
```

### ۴) اولین پست
```bash
python -m agent.cli generate                     # ساخت پست (متن+تصویر+ویدیو)
python -m agent.cli generate --topic "موضوع دلخواه"
python -m agent.cli dashboard                    # دیدن و تأیید در مرورگر → http://localhost:8000
```

---

## 📖 دستورهای ایجنت

| دستور | کار |
|---|---|
| `python -m agent.cli init` | ساخت پوشه‌ها و بررسی پیش‌نیازها |
| `python -m agent.cli doctor` | چک‌لیست کلیدها، ffmpeg، فونت، اتصال اینستاگرام |
| `python -m agent.cli generate [--topic ...] [--count N] [--publish]` | ساخت پست جدید |
| `python -m agent.cli list [--status pending]` | فهرست پست‌ها |
| `python -m agent.cli show <id>` | جزئیات یک پست (کپشن، صحنه‌ها، گفتار) |
| `python -m agent.cli approve <id>` | تأیید پیش‌نویس |
| `python -m agent.cli reject <id>` | رد پیش‌نویس |
| `python -m agent.cli publish <id>` / `--all` / `--force` | انتشار در اینستاگرام |
| `python -m agent.cli rebuild-video <id>` | ساخت مجدد ویدیو (مثلاً بعد از تغییر صدا) |
| `python -m agent.cli dashboard` | داشبورد تأیید (مرورگر) |
| `python -m agent.cli schedule` | اجرای زمان‌بند خودکار (تا وقتی باز است) |
| `python -m agent.cli ig-check` | تست اتصال اینستاگرام |
| `python -m agent.cli publish-limit` | سهمیهٔ انتشار ۲۴ ساعت گذشته |
| `python -m agent.cli refresh-token` | تمدید توکن ۶۰روزهٔ اینستاگرام |
| `python -m agent.cli upload-test` | تست میزبان آپلود ویدیو |

---

## ⚙️ تنظیمات مهم `config.yaml`

### حالت انتشار
```yaml
publish:
  mode: approve          # approve = من تأیید می‌کنم | auto = کاملاً خودکار
  schedule: ["09:30", "19:00"]     # ساعت‌های اجرای روزانه
  days: ["mon","tue","wed","thu","fri","sat","sun"]
  timezone: "Asia/Tehran"
  max_posts_per_day: 3
  first_comment: true    # گذاشتن هشتگ‌ها در اولین کامنت
```

### ویدیو و گفتار
```yaml
video:
  scenes: 4                              # تعداد صحنه هر ریلز
  voice: "fa-IR-FaridNeural"             # یا fa-IR-DilaraNeural (زن)
  voice_rate: "+8%"                      # سرعت گفتار
  max_duration: 90                       # سقف طول ریلز (تاب ریلز تا ۹۰ ثانیه)
  ken_burns: true                        # زوم آرام روی تصاویر
  bgm: "assets/music/bgm.mp3"            # موسیقی پس‌زمینه (اختیاری)
  color_primary: "#7C3AED"               # رنگ برند روی ویدیو
  font_black: "assets/fonts/Vazirmatn-Black.ttf"
```

### تولید محتوا
```yaml
content:
  text_provider: auto     # auto | gemini | openai | offline
  image_provider: auto    # auto | gemini | openai | gradient
  image_style: "cinematic editorial photography, ... no text"
```

---

## 🖥 داشبورد تأیید

```bash
python -m agent.cli dashboard        # http://localhost:8000
```
- پیش‌نمایش ویدیو، ویرایش کپشن و هشتگ‌ها (مستقیم در مرورگر)
- دکمه‌های **تأیید / رد / انتشار فوری / ساخت مجدد ویدیو / حذف**
- دکمهٔ **ساخت پست جدید** با موضوع دلخواه
- محافظت با رمز: `DASHBOARD_PASSWORD` در `.env`

---

## 🕒 اجرای دائمی (سرور)

**الف) با systemd (لینوکس)** — دو سرویس: زمان‌بند + داشبورد.

فایل `/etc/systemd/system/ig-agent.service`:
```ini
[Unit]
Description=Instagram Agent Scheduler
After=network-online.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/path/to/instagram-agent
ExecStart=/path/to/instagram-agent/.venv/bin/python -m agent.cli schedule
Restart=always
RestartSec=20

[Install]
WantedBy=multi-user.target
```

فایل `/etc/systemd/system/ig-dashboard.service` (همان، فقط `ExecStart` را بگذارید
`... -m agent.cli dashboard` و اگر فقط محلی لازم است `DASHBOARD_HOST` را در `.env`
روی `127.0.0.1` بگذارید).

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ig-agent ig-dashboard
journalctl -u ig-agent -f        # دیدن لاگ زنده
```

**ب) با Docker**
```bash
docker compose up -d       # هر دو سرویس (زمان‌بند + داشبورد)
```
**ج) بدون سرور (رایگان روی GitHub Actions)**: می‌توانید `python -m agent.cli generate --publish`
را در یک workflow با `schedule: cron` اجرا کنید؛ ولی چون ویدیوها بایتی هستند باید
آپلودر `s3` داشته باشید و مخزن خصوصی باشد. (برای شروع، گزینهٔ الف ساده‌تر است.)

---

## 🎬 ساختار خروجی هر پست
```
out/<post-id>/
├── reel.mp4          # ریلز نهایی ۱۰۸۰×۱۹۲۰ با صدا
├── cover.jpg         # کاور پیشنهادی ریلز
├── post.json         # کپشن، هشتگ، متن صحنه‌ها، گفتار
└── images/           # تصویرهای خام صحنه‌ها
```

## 🧩 ساختار پروژه
```
agent/
├── content/          # تولید متن، پرامپت‌ها و تصویرها (gemini/openai/offline)
├── video/            # رندر فریم فارسی، گویندگی edge-tts، مونتاژ ffmpeg
├── publish/          # Instagram Graph API + آپلود روی میزبان عمومی
├── pipeline.py       # خط تولید: تولید → تأیید → انتشار
├── scheduler.py      # زمان‌بند APScheduler
├── dashboard.py      # داشبورد تأیید (FastAPI)
├── store.py          # دیتابیس SQLite پست‌ها
├── rtl.py            # shaping و شکستن خط فارسی برای Pillow
└── cli.py            # خط فرمان
```

---

## ⚠️ نکات مهمی که باید بدانید

1. **اکانت حرفه‌ای لازم است.** اکانت شخصی نمی‌تواند پست منتشر کند
   (راهنمای تبدیل در [`docs/instagram-setup.md`](docs/instagram-setup.md) بخش ۰).
2. **توکن شما ۶۰ روزه است** — ایجنت یادآوری می‌کند، ولی جای‌گذاری مقدار جدید با شماست.
3. **ویژگی «انتخاب حساب» اینستاگرام** اگر روشن باشد، پست‌های API را برایت پیشنهاد
   می‌دهد؛ اگر می‌خواهی مستقیم منتشر شود، در تنظیمات اکانت خاموشش کن.
4. **لینک موقت نگذارید.** آپلودرهای `uguu/litterbox` فقط برای تست‌اند. برای استفادهٔ واقعی
   `s3` (Cloudflare R2 رایگان‌تر است) بگذارید تا ویدیو همیشه در دسترس باشد.
5. **محتوای AI را بازبینی کنید.** در حالت `approve` هیچ‌چیز بدون نظر شما منتشر نمی‌شود —
   این حالت پیش‌فرض است و توصیه می‌شود.
6. **محتوای AI را به‌عنوان واقعیت جا نزنید.** ایجنت در پرامپتش ممنوع کرده آمار جعلی بنویسد،
   ولی مسئولیت نهایی متن با شماست. با گزینهٔ `first_comment` هشتگ‌ها جدا می‌شوند (تمیزتر).
7. **موسیقی پس‌زمینه** از فایل‌های رایگان (مثل Pixabay Music یا Free Music Archive)
   در `assets/music/` بگذارید و در `config.yaml` مسیرش را بدهید.
8. **ffmpeg و فونت فارسی** با `init` بررسی می‌شوند؛ فونت وزیرمتن همراه پروژه است و در
   صورت نبودش خودکار دانلود می‌شود.

---

## 🔧 عیب‌یابی سریع

| مشکل | راه‌حل |
|---|---|
| ویدیو ساخته نمی‌شود | `python -m agent.cli doctor` → ffmpeg؟ برای تست: `--keep-temp` در `rebuild-video` |
| متن فارسی جدا/معکوس می‌آید | Pillow شما Raqm دارد؟ `python -c "from PIL import features; print(features.check('raqm'))"` — کد هر دو حالت را پوشش می‌دهد |
| صدای فارسی ندارم | `edge-tts` به اینترنت نیاز دارد؛ `video.voice` را چک کنید (fa-IR-FaridNeural / DilaraNeural) |
| انتشار خطا داد | جدول خطاها در [`docs/instagram-setup.md`](docs/instagram-setup.md) انتهای سند |
| آپلود کند است | آپلودر `s3`/R2 بگذارید (لینک موقت و سرعت کم اذیت می‌کند) |
| لاگ را کجا ببینم | `journalctl -u ig-agent -f` (سرور) یا خروجی ترمینال؛ همهٔ رخدادها در `data/agent.sqlite3` |

---

## 📄 مجوز و مسئولیت
کد این پروژه برای استفادهٔ شخصی شماست. رعایت قوانین متا و قوانین محلی محتوا با شماست.
ایجنت فقط از API رسمی استفاده می‌کند و رمز شما را ذخیره نمی‌کند.
