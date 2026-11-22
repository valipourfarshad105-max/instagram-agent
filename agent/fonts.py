"""پیدا کردن (و در صورت نیاز دانلود کردن) فونت فارسی مناسب."""
from __future__ import annotations

import io
import urllib.request
import zipfile
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

from .config import ROOT

FONT_DIR = ROOT / "assets" / "fonts"
VAZIRMATN_URL = (
    "https://github.com/rastikerdar/vazirmatn/releases/download/v33.003/vazirmatn-v33.003.zip"
)
SYSTEM_FALLBACKS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/tahoma.ttf",
]


def _download_vazirmatn() -> bool:
    """دانلود فونت وزیرمتن اگر در assets نبود (نیاز به اینترنت، یک‌بار)."""
    try:
        FONT_DIR.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(VAZIRMATN_URL, timeout=60) as resp:
            data = resp.read()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            wanted = {
                "fonts/ttf/Vazirmatn-Regular.ttf": "Vazirmatn-Regular.ttf",
                "fonts/ttf/Vazirmatn-Bold.ttf": "Vazirmatn-Bold.ttf",
                "fonts/ttf/Vazirmatn-Black.ttf": "Vazirmatn-Black.ttf",
            }
            for member, name in wanted.items():
                try:
                    with zf.open(member) as src:
                        (FONT_DIR / name).write_bytes(src.read())
                except KeyError:
                    continue
        return (FONT_DIR / "Vazirmatn-Bold.ttf").exists()
    except Exception:
        return False


def resolve_font(weight: str = "bold") -> Path | None:
    """مسیر فایل فونت: assets پروژه → فونت‌های سیستمی → دانلود → None."""
    weight = weight if weight in {"regular", "bold", "black"} else "bold"
    candidates = [
        FONT_DIR / f"Vazirmatn-{weight.capitalize()}.ttf",
        FONT_DIR / "Vazirmatn-Bold.ttf",
        FONT_DIR / "Vazirmatn-Regular.ttf",
    ]
    for path in candidates:
        if path.exists():
            return path
    if _download_vazirmatn():
        for path in candidates:
            if path.exists():
                return path
    for raw in SYSTEM_FALLBACKS:
        path = Path(raw)
        if path.exists():
            return path
    return None


@lru_cache(maxsize=64)
def load(weight: str, size: int) -> ImageFont.FreeTypeFont:
    path = resolve_font(weight)
    if path is None:
        return ImageFont.load_default()  # آخرین راه‌حل (فارسی را درست نشان نمی‌دهد)
    try:
        return ImageFont.truetype(str(path), size)
    except Exception:
        return ImageFont.load_default()
