"""ارائه‌دهندهٔ آفلاین: بدون هیچ کلید API، از قالب‌های آمادهٔ فارسی استفاده می‌کند.

برای تست کل زنجیره (ویدیو → انتشار) عالی است و همیشه به‌عنوان پشتیبان
(fallback) هم استفاده می‌شود؛ اگر سرویس هوش مصنوعی خطا داد، ایجنت از این استفاده می‌کند.
"""
from __future__ import annotations

import random

from .base import Draft, DraftScene

# قالب‌های ۴ صحنه‌ای: قلاب → مشکل → راه‌حل → جمع‌بندی
TEMPLATES: list[dict] = [
    {
        "title": "سه اشتباه رایج",
        "scenes": [
            ("یک اشتباه که فروشت را کم می‌کند", "بیا یک اشتباه رایج را با هم بررسی کنیم که خیلی از کسب‌وکارها هر روز مرتکب می‌شوند."),
            ("اول: بدون هدف پست می‌گذاری", "اشتباه اول این است که بدون هدف روشن پست می‌گذاری؛ این‌طوری انرژی می‌گذاری ولی نتیجه نمی‌گیری."),
            ("دوم: فقط از خودت می‌گویی", "اشتباه دوم این است که فقط از خودت حرف می‌زنی؛ مخاطب دنبال حل مشکل خودش است، نه معرفی تو."),
            ("سوم: پیگیری نداری", "و اشتباه سوم اینکه بعد از فروش پیگیری نمی‌کنی؛ حالا کدام را بیشتر انجام می‌دهی؟"),
        ],
    },
    {
        "title": "چرا ویدیو",
        "scenes": [
            ("ویدیو، سریع‌ترین راه دیده‌شدن", "اگر می‌خواهی در اینستاگرام دیده شوی، هیچ چیز مثل ویدیو کوتاه کار نمی‌کند."),
            ("ثانیه‌های اول همه‌چیز است", "سه ثانیهٔ اول تصمیم می‌گیرد که مخاطب بماند یا رد شود؛ پس با یک جملهٔ جذاب شروع کن."),
            ("یک نکته، یک ویدیو", "در هر ویدیو فقط یک نکته بگو؛ خواستن همه‌چیز در یک ویدیو، هیچ‌چیز را منتقل نمی‌کند."),
            ("ثبات از استعداد مهم‌تر است", "هفته‌ای سه ویدیو، یک سال پشت‌سرهم، از هر ایدهٔ ناب تک‌شات مؤثرتر است."),
        ],
    },
    {
        "title": "کپشن‌نویسی",
        "scenes": [
            ("کپشن، نیمی از پست است", "خیلی‌ها ویدیو را خوب می‌سازند اما کپشن را جدی نمی‌گیرند، در حالی که کپشن است که تعامل می‌سازد."),
            ("اولین خط، قلاب است", "خط اول کپشن باید مخاطب را نگه دارد؛ سؤال بپرس یا وعدهٔ یک نکتهٔ کاربردی بده."),
            ("کوتاه، شفاف، با فعل امر", "جمله‌های کوتاه بنویس و با فعل امر مخاطب را به عمل دعوت کن؛ همین تبدیل را بالا می‌برد."),
            ("یادت باشد: یک درخواست", "در پایان فقط یک درخواست داشته باش؛ سیو کن، کامنت بگذار، یا ذخیره کن. نه هر سه با هم."),
        ],
    },
    {
        "title": "مخاطب واقعی",
        "scenes": [
            ("برای همه نوشتن، یعنی برای هیچ‌کس", "وقتی مخاطب مشخصی نداری، پیامت به دل هیچ‌کس نمی‌نشیند."),
            ("یک نفر را تصور کن", "تصور کن فقط برای یک نفر حرف می‌زنی؛ همان‌قدری که فقط تو می‌توانی بگویی، حرف بزن."),
            ("درد او را بنویس", "به‌جای توضیح محصول، درد و دغدغهٔ مخاطب را بنویس و بعد راه‌حل را بگو."),
            ("داده‌ها نظرت را عوض می‌کنند", "هر هفته آمار را نگاه کن؛ چیزی که فکر می‌کردی خوب است ممکن است فقط خوش‌شانسی بوده باشد."),
        ],
    },
    {
        "title": "شروع کمپین",
        "scenes": [
            ("قبل از پول خرج کردن", "قبل از اینکه بودجهٔ تبلیغات را روشن کنی، این چهار مورد را چک کن."),
            ("یک: صفحهٔ مناسب", "اول مطمئن شو صفحه‌ات پیام روشنی دارد؛ تبلیغ پول، صفحهٔ نامناسب را جبران نمی‌کند."),
            ("دو: عدد واقعی", "دوم، عدد واقعی هزینهٔ جذب مشتری را بدان؛ نه حدس، نه امید."),
            ("سه: یک متغیر در هر تست", "سوم، در هر آزمایش فقط یک چیز را تغییر بده تا بفهمی چه چیزی جواب داده."),
        ],
    },
]

CAPTION_TEMPLATES = [
    "{hook}\n\n{body}\n\nذخیره کن تا بعداً به کارت بیاید.\n\n",
    "{hook}\n\n{body}\n\nنظرت چیه؟ کامنت کن.\n\n",
    "{hook}\n\n{body}\n\n{cta}\n\n",
]

IMAGE_STYLES = [
    "close-up of a modern desk with a smartphone and notebook, dramatic side light, dark background, purple accent glow",
    "conceptual photo of upward arrow made of light on a dark minimal surface, golden glow, shallow depth of field",
    "person silhouette working late at a laptop in a dark room, single warm lamp, cinematic mood",
    "minimal still life of coffee cup and open planner on dark table, moody top light, soft shadows",
]


class OfflineProvider:
    name = "offline"

    def __init__(self, cfg):
        self.cfg = cfg

    # کلماتی که برای تطبیق موضوع بی‌ارزش‌اند
    STOPWORDS = {
        "برای", "این", "اینستاگرام", "بیشتر", "چطور", "چگونه", "بهترین", "مهم‌ترین",
        "چند", "یک", "با", "از", "در", "را", "که", "های", "ها", "کار", "کاربردی",
    }

    @classmethod
    def _best_template(cls, topic: str) -> dict:
        """قالبی که با موضوع هم‌خوانی بیشتری دارد را انتخاب می‌کند (وگرنه تصادفی)."""
        words = {
            w.strip("‌,.!؟") for w in topic.replace("‌", " ").split()
            if len(w) > 3 and w not in cls.STOPWORDS
        }
        if not words:
            return random.choice(TEMPLATES)
        best, best_score = None, 0
        for template in TEMPLATES:
            haystack = template["title"] + " " + " ".join(
                text for text, _ in template["scenes"]
            )
            score = sum(1 for w in words if w in haystack)
            if score > best_score:
                best, best_score = template, score
        return best or random.choice(TEMPLATES)

    def build(self, topic: str | None = None, avoid: list[str] | None = None) -> Draft:
        cfg = self.cfg
        avoid = avoid or []
        topics = [t for t in (cfg.brand.topics or []) if t not in avoid] or list(cfg.brand.topics or [])
        topic = topic or random.choice(topics)

        template = self._best_template(topic) if topic else random.choice(TEMPLATES)
        scenes = [
            DraftScene(
                text=text,
                narration=narration,
                image_prompt=IMAGE_STYLES[i % len(IMAGE_STYLES)],
            )
            for i, (text, narration) in enumerate(template["scenes"])
        ]
        hook = scenes[0].narration
        body = "\n".join(f"• {s.text}" for s in scenes[1:])
        caption = random.choice(CAPTION_TEMPLATES).format(
            hook=hook, body=body, cta=cfg.brand.cta
        ).strip()
        hashtags = list(cfg.brand.hashtags_base or [])
        return Draft(
            topic=topic,
            title=template["title"],
            scenes=scenes,
            caption=caption,
            hashtags=hashtags,
            provider=self.name,
            meta={"template": template["title"]},
        )
