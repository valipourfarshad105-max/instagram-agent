# راهنمای عملیاتی — از صفر تا پست زنده

نسخهٔ کوتاه و کاربردی. هر مرحله را به ترتیب انجام دهید.

---

## مرحلهٔ ۱ — همین حالا، بدون هیچ کلیدی (۵ دقیقه)

هدف: مطمئن شویم کل زنجیره روی سیستم شما کار می‌کند.

```bash
cd instagram-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

python -m agent.cli init        # ffmpeg و فونت را چک می‌کند
python -m agent.cli generate    # یک ریلز آزمایشی با قالب آفلاین می‌سازد
python -m agent.cli dashboard   # http://localhost:8000
```

در داشبورد ویدیو را ببینید. اگر متن فارسی درست و صدا روان بود ⇒ زیرساخت آماده است ✅

> اگر صدای گوینده نیامد: اینترنت را چک کنید (edge-tts آفلاین کار نمی‌کند).

---

## مرحلهٔ ۲ — کیفیت محتوا را بالا ببرید (۱۰ دقیقه)

### الف) یک کلید هوش مصنوعی بگیرید (پیشنهاد: Gemini)
1. برو به <https://aistudio.google.com/apikey>
2. **Create API key** → کپی کنید
3. در `.env`: `GEMINI_API_KEY=...`

اینجا از پلن رایگان هم می‌توانید استفاده کنید (محدودیت نرخ دارد ولی برای چند پست در روز کافی است).
اگر ترجیح می‌دهید OpenAI: `OPENAI_API_KEY=...` (تولید تصویر در OpenAI پول‌بر است، Gemini گزینهٔ ارزان‌تری است).

### ب) برند و لحن را در `config.yaml` تنظیم کنید
مهم‌ترین‌ها: `brand.name`، `brand.handle`، `brand.niche`، `brand.audience`، `brand.tone`،
`brand.topics`، `brand.cta` — این‌ها مستقیم به پرامپت مدل می‌روند.

### ج) تست
```bash
python -m agent.cli generate --topic "موضوع حوزهٔ خودتان"
```
کپشن و سناریو را با حالت آفلاین مقایسه کنید — تفاوت واضح است.

---

## مرحلهٔ ۳ — اتصال اینستاگرام (۲۰ دقیقه)

راهنمای کامل: [`instagram-setup.md`](instagram-setup.md)

خلاصه:
1. اکانت را به **Business/Creator** تبدیل کنید (اگر شخصی است).
2. اپ متا بسازید → محصول Instagram → توکن با دسترسی
   `instagram_business_basic` + `instagram_business_content_publish`.
3. `IG_USER_ID` را از `graph.instagram.com/v23.0/me` بگیرید.
4. در `.env` بگذارید و تست کنید:
   ```bash
   python -m agent.cli ig-check
   ```

---

## مرحلهٔ ۴ — میزبانی ویدیو (۱۰ دقیقه، مهم برای پایداری)

اینستاگرام ویدیو را خودش از URL دانلود می‌کند؛ اگر لینک بمیرد، پست منتشر نمی‌شود.

**گزینهٔ پیشنهادی: Cloudflare R2** (ارزان/رایگان)
1. در Cloudflare → R2 → یک bucket بسازید (مثلاً `ig-media`)
2. یک API Token با دسترسی Object Read & Write بسازید
3. bucket را Public کنید یا یک دامنه وصل کنید
4. در `.env`:
```env
UPLOADER=s3
S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
S3_REGION=auto
S3_BUCKET=ig-media
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
S3_PUBLIC_BASE_URL=https://pub-xxxx.r2.dev     # یا دامنهٔ خودتان
```
تست: `python -m agent.cli upload-test` → لینک را در مرورگر باز کنید.

> AWS S3 هم همین پارامترها را دارد (فقط `S3_ENDPOINT_URL` را خالی بگذارید).

---

## مرحلهٔ ۵ — اولین انتشار واقعی

```bash
python -m agent.cli generate --topic "اولین پست من"
python -m agent.cli list                    # شناسهٔ پست را بگیرید
python -m agent.cli approve <post-id>
python -m agent.cli publish <post-id>       # 🚀
```
یا همه از داشبورد با دکمه‌ها.

بعد از انتشار، `media_id` در دیتابیس ثبت می‌شود؛ برای دیدن:
```bash
python -m agent.cli show <post-id>
```

---

## مرحلهٔ ۶ — خودکارسازی

### حالت تأیید دستی (پیشنهادی برای شروع)
```yaml
publish:
  mode: approve
  schedule: ["09:30", "19:00"]
```
```bash
python -m agent.cli schedule      # این را روشن بگذارید (systemd/دیزنی)
python -m agent.cli dashboard     # این را هم برای تأییدها باز بگذارید
```
هر ساعت ۹:۳۰ و ۱۹:۰۰ یک پیش‌نویس ساخته می‌شود؛ شما در داشبورد تأیید می‌کنید و
زمان‌بند هر ۱۵ دقیقه پست‌های تأییدشده را منتشر می‌کند.

### حالت کاملاً خودکار
```yaml
publish:
  mode: auto
  max_posts_per_day: 2         # محافظت در برابر خطای انسانی
```
از این حالت بعد از یکی دو هفته کار با حالت تأیید استفاده کنید (وقتی به کیفیت
خروجی‌ها اطمینان کردید).

### اجرای دائمی
```bash
sudo systemctl enable --now ig-agent ig-dashboard    # نمونهٔ سرویس در README
```

---

## نگه‌داری ماهانه

| کار | دستور | هر چند وقت |
|---|---|---|
| تمدید توکن اینستاگرام | `refresh-token` و به‌روزرسانی `.env` | هر ۵۰ روز |
| چک سهمیه | `publish-limit` | ماهی یک‌بار |
| بررسی خطاها | `list --status failed` | هفتگی |
| پاک‌سازی ویدیوهای قدیمی | پوشهٔ `out/` را برای پست‌های منتشرشدهٔ قدیمی خالی کنید | ماهی یک‌بار |
| به‌روزرسانی هشتگ‌ها | `brand.hashtags_base` در config | ماهی یک‌بار |

---

## نقشهٔ راه پیشنهادی برای بهتر شدن محتوا

1. **هفتهٔ اول**: حالت آفلاین → بعد Gemini؛ ۱ پست در روز، حالت تأیید دستی.
   هر پست را کامل بخوانید و در `config.yaml` لحن را اصلاح کنید.
2. **هفتهٔ دوم**: موضوعات پرطرفدار را به `brand.topics` اضافه کنید؛ صدای گوینده را عوض کنید
   (`fa-IR-DilaraNeural`) و مقایسه کنید.
3. **هفتهٔ سوم**: موسیقی پس‌زمینه اضافه کنید (`assets/music/bgm.mp3`)، رنگ برند و لوگو بگذارید.
4. **هفتهٔ چهارم**: اگر کیفیت راضی‌کننده بود، `mode: auto` را با `max_posts_per_day: 2` روشن کنید.
5. **بعد از آن**: می‌توانید گزارش اینسایت پست‌ها را هم به ایجنت اضافه کنید
   (`GET /{ig-user-id}/media?fields=like_count,comments_count` را در `publish/instagram.py` صدا بزنید)
   و به مدل بگویید از موضوعات پربازده‌تر ایده بگیرد.
