"""پرامپت‌های مشترک برای مدل‌های زبانی (فارسی)."""
from __future__ import annotations

import json

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"},
        "title": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "narration": {"type": "string"},
                    "image_prompt": {"type": "string"},
                },
                "required": ["text", "narration", "image_prompt"],
            },
        },
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["topic", "title", "scenes", "caption", "hashtags"],
}


def build_system_prompt(cfg) -> str:
    brand = cfg.brand
    return (
        "تو یک استراتژیست محتوای حرفه‌ای اینستاگرام فارسی‌زبان هستی و برای یک پیج "
        "ویدیوهای کوتاه (ریلز) می‌نویسی.\n\n"
        f"دربارهٔ پیج:\n"
        f"- نام: {brand.name}\n"
        f"- آی‌دی: {brand.handle}\n"
        f"- حوزهٔ فعالیت: {brand.niche}\n"
        f"- مخاطب هدف: {brand.audience}\n"
        f"- لحن و سبک: {brand.tone}\n\n"
        "قواعد نوشتن:\n"
        "۱. کاملاً فارسی، محاوره‌ای ولی محترمانه و حرفه‌ای. از کلمات انگلیسی رایج "
        "(مثل پست، ویدیو، کامنت) در صورت لزوم استفاده کن، ولی ترجمهٔ افراطی نکن.\n"
        "۲. لحن باید انسانی باشد؛ از کلیشه‌های تبلیغاتی و وعده‌های اغراق‌آمیز پرهیز کن.\n"
        "۳. هیچ آمار یا عددی که از آن مطمئن نیستی ننویس.\n"
        "۴. ساختار روایی هر ریلز: قلاب قوی در صحنهٔ اول، سپس یک نکتهٔ کاربردی در هر صحنه، "
        "و صحنهٔ آخر با یک فراخوان به اقدام.\n"
        "۵. هر جمله کوتاه باشد تا گویندهٔ فارسی روان بخواند؛ از جملات تودرتو پرهیز کن.\n"
        "۶. اگر کاراکتر لاتین یا عدد در متن لازم است، ساده و کوتاه بنویس.\n"
        "۷. کپشن با هوک شروع شود، بدنهٔ کوتاه داشته باشد، و در پایان یک درخواست روشن.\n"
        "۸. هشتگ‌ها فارسی دست‌ساز مرتبط با موضوع باشند (۸ تا ۱۲ عدد).\n"
    )


def build_user_prompt(cfg, topic: str | None, avoid: list[str] | None = None) -> str:
    brand = cfg.brand
    scenes_n = int(cfg.video.scenes)
    forbidden = brand.forbidden or []
    parts = []
    if topic:
        parts.append(f"موضوع این ریلز: «{topic}»")
    else:
        parts.append(
            "موضوع را خودت از این حوزه انتخاب کن و از تکرار موضوعات قبلی بپرهیز: "
            f"«{brand.niche}». می‌توانی از این فهرست هم ایده بگیری: "
            + "، ".join(f"«{t}»" for t in (brand.topics or [])[:8])
        )
    if avoid:
        parts.append("این موضوعات اخیراً استفاده شده‌اند، سراغ‌شان نرو: " + "، ".join(f"«{t}»" for t in avoid))
    parts.append(
        f"\nیک ریلز فارسی با دقیقاً {scenes_n} صحنه بساز و خروجی را فقط به‌صورت JSON "
        f"مطابق این ساختار بده:\n{json.dumps(DRAFT_SCHEMA, ensure_ascii=False, indent=2)}\n\n"
        "راهنمای هر فیلد:\n"
        "- text: متن روی تصویر در هر صحنه؛ حداکثر ۶ کلمه، ضربه‌ای و خوانا (بدون نقطه در آخر).\n"
        "- narration: جمله‌ای که گوینده می‌خواند؛ بین ۱۰ تا ۲۲ کلمه، محاوره‌ای و روان.\n"
        "- image_prompt: پرامپت انگلیسی تصویرسازی برای همان صحنه. سبک: "
        f"{cfg.content.image_style} — حتماً انتهای پرامپت قید کن که هیچ متن و لوگویی در تصویر نباشد.\n"
        "- caption: کپشن فارسی آمادهٔ انتشار (بدون هشتگ)، حداکثر ۵۰۰ کاراکتر.\n"
        f"- hashtags: آرایه‌ای از هشتگ‌ها با علامت # (شامل این‌ها هم باشد: "
        f"{'، '.join(brand.hashtags_base or [])})."
    )
    if forbidden:
        parts.append("این عبارت‌ها را هرگز ننویس: " + "، ".join(f"«{f}»" for f in forbidden))
    parts.append("\nخروجی را فقط با JSON برگردان، بدون هیچ توضیح اضافه یا بلوک کد.")
    return "\n\n".join(parts)
