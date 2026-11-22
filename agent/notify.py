"""اعلان‌ها: تلگرام و لاگ خطی.

اگر TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID در .env باشند، در حالت تأیید دستی
پیش‌نویس جدید با لینک داشبورد به تلگرام شما می‌آید.
"""
from __future__ import annotations

import logging
import sys

import requests

from .config import env

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def get_logger(name: str = "agent") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


log = get_logger()


def telegram_send(text: str, buttons: list[tuple[str, str]] | None = None) -> bool:
    token, chat_id = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        return False
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": True}
    if buttons:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": label, "url": url}] for label, url in buttons]
        }
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=20
        )
        return response.status_code < 400
    except Exception as exc:  # noqa: BLE001
        log.warning("ارسال تلگرام ناموفق بود: %s", exc)
        return False


def notify_new_draft(post, dashboard_url: str = "") -> None:
    """اعلان «پیش‌نویس آمادهٔ تأیید است»."""
    caption_preview = (post.caption or "")[:400]
    text = (
        f"🎬 <b>پیش‌نویس جدید آمادهٔ تأیید</b>\n\n"
        f"<b>موضوع:</b> {post.topic}\n"
        f"<b>کپشن:</b>\n{caption_preview}\n\n"
        f"<code>{post.id}</code>"
    )
    buttons = []
    if dashboard_url:
        buttons.append(("✅ باز کردن در داشبورد", f"{dashboard_url.rstrip('/')}/post/{post.id}"))
    if not telegram_send(text, buttons):
        log.info("پیش‌نویس %s آمادهٔ تأیید است (تلگرام تنظیم نشده).", post.id)


def notify_published(post, permalink: str = "") -> None:
    text = (
        f"🚀 <b>منتشر شد!</b>\n\n<b>موضوع:</b> {post.topic}\n"
        f"<code>media_id: {post.ig_media_id}</code>"
    )
    if permalink:
        text += f"\n{permalink}"
    telegram_send(text)


def notify_error(post, message: str) -> None:
    telegram_send(f"⚠️ <b>خطا در ایجنت</b>\n\n<code>{post.id if post else '-'}</code>\n{message[:500]}")
