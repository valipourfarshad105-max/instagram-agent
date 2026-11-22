"""ابزارهای متن فارسی: اتصال حروف (shaping)، راست‌به‌چپ، شکستن خط، اعداد فارسی.

Pillow به‌تنهایی حروف فارسی را جدا از هم می‌کشد و ترتیب راست‌به‌چپ را هم
رعایت نمی‌کند؛ پس متن قبل از رسم باید reshape و bidi شود.
"""
from __future__ import annotations

import re
from typing import Iterable, List

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import ImageFont

_RESHAPER = arabic_reshaper.ArabicReshaper(
    configuration={
        "delete_harakat": False,
        "support_ligatures": True,
        "use_unshaped_instead_of_isolated": True,
    }
)

try:  # اگر Pillow با Raqm/harfbuzz کامپایل شده باشد، خودش shaping و bidi را انجام می‌دهد
    from PIL import features as _pil_features

    HAS_RAQM: bool = bool(_pil_features.check("raqm"))
except Exception:  # noqa: BLE001
    HAS_RAQM = False

_FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"


def shape(text: str) -> str:
    """متن منطقی فارسی → رشتهٔ آمادهٔ رسم در Pillow.

    - اگر Pillow موتور Raqm داشته باشد (حالت رایج در نسخه‌های جدید)، متن را
      بدون تغییر برمی‌گردانیم؛ چون خود Pillow اتصال حروف و راست‌به‌چپ را انجام می‌دهد
      و دست‌کاری دوباره متن را معکوس می‌کند.
    - در غیر این صورت از arabic_reshaper و python-bidi استفاده می‌کنیم.
    """
    if not text:
        return ""
    text = normalize(text)
    if HAS_RAQM:
        return text
    return get_display(_RESHAPER.reshape(text))


def to_fa_digits(text: str) -> str:
    out = []
    for ch in str(text):
        out.append(_FA_DIGITS[int(ch)] if ch.isdigit() and ch.isascii() else ch)
    return "".join(out)


def normalize(text: str) -> str:
    """یکسان‌سازی حروف عربی/فارسی و فاصله‌ها."""
    if not text:
        return ""
    text = text.replace("ي", "ی").replace("ك", "ک").replace("ﻻ", "لا")
    text = re.sub(r"[ \t\u200c]{2,}", " ", text)
    return text.strip()


def strip_emoji(text: str) -> str:
    return re.sub(
        "[" "\U0001F300-\U0001FAFF" "\U00002700-\U000027BF" "\U0001F1E0-\U0001F1FF" "\u2600-\u26FF" "]+",
        "",
        text or "",
    ).strip()


def measure(font: ImageFont.FreeTypeFont, text: str) -> float:
    """عرض متن شکل‌گرفته بر حسب پیکسل (نسخه‌های قدیمی Pillow هم پشتیبانی می‌شوند)."""
    shaped = shape(text)
    if hasattr(font, "getlength"):
        return font.getlength(shaped)
    return font.getsize(shaped)[0]  # type: ignore[attr-defined]


def _hard_split(font: ImageFont.FreeTypeFont, word: str, max_width: float) -> List[str]:
    """کلمهٔ بسیار بلند را به زور می‌شکند."""
    chunks, current = [], ""
    for ch in word:
        if measure(font, current + ch) <= max_width or not current:
            current += ch
        else:
            chunks.append(current)
            current = ch
    if current:
        chunks.append(current)
    return chunks


def wrap(text: str, font: ImageFont.FreeTypeFont, max_width: float, max_lines: int = 0) -> List[str]:
    """شکستن متن فارسی به خطوط، بر اساس عرض واقعی متن شکل‌گرفته."""
    text = normalize(text).replace("\n", " ")
    if not text:
        return []
    lines: List[str] = []
    for word in text.split(" "):
        if not word:
            continue
        if measure(font, word) > max_width:
            for chunk in _hard_split(font, word, max_width):
                lines.append(chunk)
            continue
        candidate = f"{lines[-1]} {word}" if lines else word
        if measure(font, candidate) <= max_width:
            if lines:
                lines[-1] = candidate
            else:
                lines.append(candidate)
        else:
            lines.append(word)
    if max_lines and len(lines) > max_lines:
        kept = lines[:max_lines]
        while kept and measure(font, kept[-1] + "…") > max_width:
            kept[-1] = kept[-1].rsplit(" ", 1)[0] if " " in kept[-1] else kept[-1][:-1]
        kept[-1] = kept[-1].rstrip() + "…"
        lines = kept
    return lines


def fit_font(
    text: str,
    font_loader,
    max_width: float,
    max_height: float,
    start_size: int,
    min_size: int = 34,
    max_lines: int = 4,
):
    """بزرگ‌ترین اندازهٔ فونت که متن در کادر مشخص جا شود."""
    size = start_size
    while size > min_size:
        font = font_loader(size)
        lines = wrap(text, font, max_width, max_lines)
        line_h = size * 1.45
        if len(lines) * line_h <= max_height:
            return font, lines
        size -= 4
    font = font_loader(min_size)
    return font, wrap(text, font, max_width, max_lines)


def join_hashtags(tags: Iterable[str]) -> str:
    seen, out = set(), []
    for tag in tags:
        tag = (tag or "").strip().replace(" ", "_")
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = "#" + tag
        if tag.lower() not in seen:
            seen.add(tag.lower())
            out.append(tag)
    return " ".join(out)
