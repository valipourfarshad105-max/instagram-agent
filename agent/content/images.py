"""ساخت تصویر صحنه‌ها: هوش مصنوعی (Gemini/OpenAI) یا پس‌زمینهٔ گرادیانی (پشتیبان)."""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from ..config import env
from ..notify import get_logger

log = get_logger("images")


# ───────────────────────── پشتیبان: گرادیان رویه‌ای ─────────────────────────
def _hex_rgb(value: str) -> tuple[int, int, int]:
    value = (value or "#7C3AED").lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return (124, 58, 237)


def gradient_image(out_path: Path, width: int, height: int, seed: int = 0,
                   color_a: str = "#0B1220", color_b: str = "#7C3AED",
                   accent: str = "#F59E0B") -> Path:
    """پس‌زمینهٔ گرادیانی تیره با هالهٔ نوری — همیشه در دسترس، بدون کلید API.

    این تصویر در حالت عادی زیر متن فارسی می‌رود، پس تا حد امکان ساده و کم‌شلوغ است.
    """
    rng = random.Random(seed or random.randint(0, 10**6))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    a, b = _hex_rgb(color_a), _hex_rgb(color_b)
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    # گرادیان عمودی ملایم (روی تصویر کوچک ساخته و بزرگ می‌شود: سریع)
    small_h = 256
    grad = Image.new("RGB", (1, small_h))
    for y in range(small_h):
        t = y / (small_h - 1)
        t = t ** 1.4
        grad.putpixel((0, y), tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))
    img = grad.resize((width, height), Image.BILINEAR)

    # هالهٔ نوری رنگی
    glow = Image.new("L", (width // 2, height // 2), 0)
    gdraw = ImageDraw.Draw(glow)
    cx, cy = rng.randint(int(width * 0.2), int(width * 0.8)) // 2, rng.randint(int(height * 0.12), int(height * 0.45)) // 2
    radius = rng.randint(int(min(width, height) * 0.25), int(min(width, height) * 0.5)) // 2
    gdraw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=190)
    glow = glow.filter(ImageFilter.GaussianBlur(radius // 2 + 8)).resize((width, height), Image.BILINEAR)
    img = Image.composite(Image.new("RGB", (width, height), _hex_rgb(accent)), img, glow.point(lambda v: int(v * 0.55)))

    # بافت نویز خیلی ملایم
    noise = Image.effect_noise((width, height), 12).convert("L").point(lambda v: 128 + (v - 128) // 6)
    img = Image.blend(img, Image.merge("RGB", (noise, noise, noise)), 0.05)

    # وینیت
    vignette = Image.new("L", (width, height), 0)
    vdraw = ImageDraw.Draw(vignette)
    vdraw.ellipse(
        (-width * 0.25, -height * 0.15, width * 1.25, height * 1.15), fill=210
    )
    vignette = vignette.filter(ImageFilter.GaussianBlur(160))
    img = Image.composite(img, Image.new("RGB", (width, height), (4, 6, 12)),
                          vignette.point(lambda v: min(255, v + 25)))
    img = img.filter(ImageFilter.GaussianBlur(0.4))
    img.save(out_path, "JPEG", quality=92)
    return out_path


# ───────────────────────────── انتخاب ارائه‌دهنده ─────────────────────────────
def _resolve_provider(cfg) -> str:
    requested = (cfg.content.image_provider or "auto").lower()
    if requested != "auto":
        return requested
    if env("GEMINI_API_KEY"):
        return "gemini"
    if env("OPENAI_API_KEY"):
        return "openai"
    return "gradient"


def generate_image(prompt: str, out_path: Path, cfg, index: int = 0) -> Path:
    """تصویر یک صحنه را می‌سازد. در صورت هر خطایی، گرادیان پشتیبان برمی‌گرداند."""
    width, height = int(cfg.video.width), int(cfg.video.height)
    provider = _resolve_provider(cfg)

    if provider in ("gemini", "openai"):
        try:
            from .gemini_provider import GeminiProvider
            from .openai_provider import OpenAIProvider

            full_prompt = (
                f"{prompt}\n\nAspect ratio 9:16 vertical. "
                "No text, no letters, no words, no logo, no watermark anywhere in the image."
            )
            if provider == "gemini":
                path = GeminiProvider(cfg).image(full_prompt, out_path)
            else:
                path = OpenAIProvider(cfg).image(full_prompt, out_path)
            _normalize(path, width, height)
            return path
        except Exception as exc:  # noqa: BLE001
            log.warning("تولید تصویر با %s ناموفق بود (%s) — استفاده از پس‌زمینهٔ گرادیانی.", provider, exc)

    colors = [(cfg.video.color_primary, cfg.video.color_secondary)]
    primary, secondary = colors[0]
    return gradient_image(
        out_path, width, height, seed=index + 1,
        color_a="#0A0F1E", color_b=primary, accent=secondary,
    )


def _normalize(path: Path, width: int, height: int) -> None:
    """تصویر را به قاب عمودی ۹:۱۶ برش می‌زند و بهینه ذخیره می‌کند."""
    try:
        with Image.open(path) as img:
            img = img.convert("RGB")
            target_ratio = width / height
            w, h = img.size
            ratio = w / h
            if ratio > target_ratio:  # عریض‌تر از حد → از وسط برش
                new_w = int(h * target_ratio)
                left = (w - new_w) // 2
                img = img.crop((left, 0, left + new_w, h))
            elif ratio < target_ratio:  # بلندتر → برش عمودی
                new_h = int(w / target_ratio)
                top = (h - new_h) // 2
                img = img.crop((0, top, w, top + new_h))
            img = img.resize((width, height), Image.LANCZOS)
            img.save(path, "JPEG", quality=92)
    except Exception as exc:  # noqa: BLE001
        log.warning("نرمال‌سازی تصویر ناموفق بود: %s", exc)


def cover_from_frame(video_path: Path, out_path: Path, at_second: float = 1.0) -> Path | None:
    """گرفتن یک فریم از ویدیو برای کاور ریلز."""
    import subprocess

    from ..video.ffmpeg import ffmpeg_bin

    try:
        subprocess.run(
            [ffmpeg_bin(), "-y", "-ss", f"{at_second}", "-i", str(video_path),
             "-frames:v", "1", "-q:v", "2", str(out_path)],
            check=True, capture_output=True, timeout=120,
        )
        return out_path if out_path.exists() else None
    except Exception as exc:  # noqa: BLE001
        log.warning("گرفتن کاور ناموفق بود: %s", exc)
        return None


def make_placeholder_banner(text: str, out_path: Path, cfg) -> Path:
    """بنر سادهٔ گرادیانی (برای تست یا جای‌گذاری لوگو)."""
    gradient_image(out_path, int(cfg.video.width), int(cfg.video.height), seed=7,
                   color_a="#0A0F1E", color_b=cfg.video.color_primary,
                   accent=cfg.video.color_secondary)
    return out_path


__all__ = ["generate_image", "gradient_image", "cover_from_frame", "make_placeholder_banner", "math"]
