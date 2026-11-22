"""رندر فریم هر صحنه با Pillow: تصویر پس‌زمینه + متن فارسی + هویت برند.

نکته‌های مهم:
- متن فارسی قبل از رسم با arabic_reshaper و python-bidi آماده می‌شود (ماژول rtl).
- فریم‌ها با ضریب بزرگ‌نمایی (supersample) رندر می‌شوند تا zoompan کیفیت بهتری بدهد.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter

from .. import rtl
from ..fonts import load as load_font


def _hex(value: str, alpha: int | None = None):
    value = (value or "#7C3AED").lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    try:
        rgb = tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        rgb = (124, 58, 237)
    return rgb + (alpha,) if alpha is not None else rgb


def _cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """تصویر را بدون کشیدگی، وسط‌چین و کامل‌کنندهٔ کادر می‌کند."""
    tw, th = size
    w, h = image.size
    scale = max(tw / w, th / h)
    new = image.resize((max(1, int(w * scale + 0.5)), max(1, int(h * scale + 0.5))), Image.LANCZOS)
    left = (new.width - tw) // 2
    top = (new.height - th) // 2
    return new.crop((left, top, left + tw, top + th))


def _rounded(draw: ImageDraw.ImageDraw, box, radius: int, fill) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def render_scene_frame(
    scene: Any,
    index: int,
    total: int,
    cfg,
    out_path: Path,
    supersample: int = 2,
) -> Path:
    """یک فریم تمام‌صفحه برای صحنه می‌سازد و مسیر PNG را برمی‌گرداند."""
    width = int(cfg.video.width) * supersample
    height = int(cfg.video.height) * supersample
    brand = cfg.brand
    primary = _hex(cfg.video.color_primary)
    secondary = _hex(cfg.video.color_secondary)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # ---------- پس‌زمینه ----------
    if scene.image_path and Path(scene.image_path).exists():
        with Image.open(scene.image_path) as raw:
            canvas = _cover(raw.convert("RGB"), (width, height))
        canvas = canvas.filter(ImageFilter.GaussianBlur(1.2 * supersample))
    else:
        canvas = Image.new("RGB", (width, height), _hex("#0A0F1E"))

    # ---------- سایهٔ تیره برای خوانایی متن ----------
    shade = Image.new("L", (width, height), 0)
    sdraw = ImageDraw.Draw(shade)
    for y in range(0, height, 4):  # گرادیان عمودی: بالا ملایم، پایین تیره
        t = y / height
        alpha = int(20 + 150 * max(0.0, (t - 0.30) / 0.70) ** 1.2 + 40 * t)
        sdraw.rectangle((0, y, width, y + 4), fill=min(255, alpha))
    canvas = Image.composite(Image.new("RGB", (width, height), (6, 8, 16)), canvas, shade)

    draw = ImageDraw.Draw(canvas, "RGBA")
    margin = int(width * 0.075)

    # ---------- چیپ برند (بالا) ----------
    chip_h = int(height * 0.036)
    chip_font = load_font("bold", int(chip_h * 0.52))
    handle_text = brand.handle if str(brand.handle).startswith("@") else f"@{brand.handle}"
    text_w = rtl.measure(chip_font, handle_text)
    chip_w = text_w + chip_h * 1.1
    chip_y = int(height * 0.055)
    _rounded(draw, (margin, chip_y, margin + chip_w, chip_y + chip_h), chip_h // 2,
             primary + (235,))
    draw.text((margin + chip_w / 2, chip_y + chip_h / 2), rtl.shape(handle_text),
              font=chip_font, fill=(255, 255, 255, 255), anchor="mm")

    # ---------- نقطه‌های پیشرفت صحنه ----------
    dot_r = int(width * 0.007)
    gap = int(dot_r * 2.6)
    total_w = (total - 1) * gap
    start_x = width // 2 - total_w // 2
    dot_y = chip_y + chip_h // 2
    for i in range(total):
        color = secondary + (255,) if i == index else (255, 255, 255, 90)
        cx = start_x + i * gap
        draw.ellipse((cx - dot_r, dot_y - dot_r, cx + dot_r, dot_y + dot_r), fill=color)

    # ---------- متن اصلی ----------
    text = rtl.to_fa_digits(rtl.normalize(scene.text))
    max_w = width - margin * 2
    from .. import rtl as _rtl  # local alias برای خوانایی

    font, lines = _rtl.fit_font(
        text, lambda size: load_font("black", size),
        max_width=max_w, max_height=int(height * 0.33),
        start_size=int(width * 0.125), min_size=int(width * 0.06), max_lines=4,
    )
    line_h = int(font.size * 1.42)
    block_h = line_h * len(lines)
    base_y = int(height * 0.775) - block_h

    # خط تأکید بالای متن
    accent_w, accent_h = int(width * 0.14), int(width * 0.011)
    draw.rounded_rectangle(
        (width // 2 - accent_w // 2, base_y - int(height * 0.045),
         width // 2 + accent_w // 2, base_y - int(height * 0.045) + accent_h),
        radius=accent_h // 2, fill=secondary + (255,),
    )

    # سایهٔ نرم پشت متن برای خوانایی روی هر پس‌زمینه‌ای
    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sdraw2 = ImageDraw.Draw(shadow)
    for i, line in enumerate(lines):
        y = base_y + i * line_h + line_h // 2
        sdraw2.text((width // 2 + 3 * supersample, y + 3 * supersample), _rtl.shape(line),
                    font=font, fill=(0, 0, 0, 190), anchor="mm")
    shadow = shadow.filter(ImageFilter.GaussianBlur(3 * supersample))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow)
    draw = ImageDraw.Draw(canvas, "RGBA")
    for i, line in enumerate(lines):
        y = base_y + i * line_h + line_h // 2
        draw.text((width // 2, y), _rtl.shape(line), font=font,
                  fill=(255, 255, 255, 255), anchor="mm")

    # ---------- پایین: نام پیج + فراخوان ----------
    foot_font = load_font("medium", int(width * 0.036))
    name_text = rtl.shape(brand.name)
    foot_y = int(height * 0.925)
    draw.text((width // 2, foot_y), name_text, font=foot_font,
              fill=(255, 255, 255, 230), anchor="mm")
    if brand.cta and index == total - 1:
        cta_font = load_font("regular", int(width * 0.030))
        draw.text((width // 2, foot_y + int(height * 0.035)), rtl.shape(brand.cta),
                  font=cta_font, fill=secondary + (255,), anchor="mm")

    # ---------- لوگو (اختیاری) ----------
    logo = getattr(cfg.video, "logo", "")
    if logo:
        logo_path = cfg.get_path("logo") if hasattr(cfg, "get_path") else None
        candidate = Path(logo) if logo_path is None else logo_path
        if candidate.exists():
            with Image.open(candidate) as lg:
                lg = lg.convert("RGBA")
                target_w = int(width * 0.16)
                lg = lg.resize((target_w, int(lg.height * target_w / lg.width)), Image.LANCZOS)
                canvas.alpha_composite(lg, (width - margin - target_w, chip_y))

    canvas.convert("RGB").save(out_path, "PNG")
    return out_path
