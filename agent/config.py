"""بارگذاری تنظیمات: config.yaml + متغیرهای محیطی (.env)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

DEFAULTS: dict[str, Any] = {
    "brand": {
        "name": "پیج من",
        "handle": "@my.page",
        "niche": "کسب‌وکار",
        "audience": "مخاطب فارسی‌زبان",
        "tone": "خودمانی و کاربردی",
        "language": "fa",
        "cta": "سیو کن",
        "emoji": True,
        "topics": ["یک نکتهٔ کاربردی در حوزهٔ کسب‌وکار"],
        "hashtags_base": ["#اینستاگرام"],
        "forbidden": [],
    },
    "video": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "scenes": 4,
        "transition": 0.5,
        "lead_in": 0.35,
        "tail_gap": 0.75,
        "ken_burns": True,
        "max_duration": 90,
        "voice": "fa-IR-FaridNeural",
        "voice_rate": "+8%",
        "voice_volume": "+0%",
        "bgm": "",
        "bgm_volume": 0.12,
        "color_primary": "#7C3AED",
        "color_secondary": "#F59E0B",
        "font_regular": "assets/fonts/Vazirmatn-Regular.ttf",
        "font_bold": "assets/fonts/Vazirmatn-Bold.ttf",
        "font_black": "assets/fonts/Vazirmatn-Black.ttf",
        "logo": "",
    },
    "content": {
        "text_provider": "auto",
        "image_provider": "auto",
        "model_text": "",
        "model_image": "",
        "ideas_per_run": 1,
        "image_style": "cinematic, moody, minimal, high contrast, vertical 9:16, no text",
    },
    "publish": {
        "mode": "approve",
        "schedule": ["09:30", "19:00"],
        "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        "timezone": "Asia/Tehran",
        "max_posts_per_day": 3,
        "share_to_feed": True,
        "first_comment": True,
        "uploader": "",
        "retry": 3,
    },
    "paths": {"out": "out", "data": "data", "db": "data/agent.sqlite3"},
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class Cfg(dict):
    """dict با دسترسی نقطه‌ای: cfg.video.fps"""

    def __getattr__(self, item: str) -> Any:
        try:
            value = self[item]
        except KeyError as exc:  # pragma: no cover
            raise AttributeError(item) from exc
        return Cfg(value) if isinstance(value, dict) else value

    def get_path(self, key: str) -> Path:
        """مسیر نسبی داخل کلید را نسبت به ریشهٔ پروژه برمی‌گرداند.

        اگر کلید در همین سطح نبود، داخل بخش «paths» جست‌وجو می‌کند.
        """
        if key in self:
            raw = self[key]
        else:
            raw = (self.get("paths") or {}).get(key, key)
        path = Path(str(raw)).expanduser()
        return path if path.is_absolute() else (ROOT / path)


def load_config(config_file: str | Path | None = None) -> Cfg:
    load_dotenv(ROOT / ".env", override=False)
    path = Path(config_file) if config_file else ROOT / "config.yaml"
    user_cfg: dict = {}
    if path.exists():
        with open(path, encoding="utf-8") as fh:
            user_cfg = yaml.safe_load(fh) or {}
    cfg = Cfg(_deep_merge(DEFAULTS, user_cfg))

    # مقادیر محیطی که کانفیگ را override می‌کنند
    if os.getenv("UPLOADER"):
        pass  # در uploader.py خوانده می‌شود
    if not cfg.publish.uploader:
        cfg["publish"]["uploader"] = os.getenv("UPLOADER", "uguu")
    return cfg


def env(key: str, default: str = "") -> str:
    value = os.getenv(key, default)
    return value.strip() if isinstance(value, str) else value


def ensure_dirs(cfg: Cfg) -> None:
    for key in ("out", "data"):
        cfg.get_path(key).mkdir(parents=True, exist_ok=True)
    cfg.get_path("db").parent.mkdir(parents=True, exist_ok=True)
