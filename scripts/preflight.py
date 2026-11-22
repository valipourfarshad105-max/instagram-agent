#!/usr/bin/env python3
"""پیش‌بررسی سریع: بدون ساختن پست، همهٔ زیرساخت‌ها را چک می‌کند.

    python scripts/preflight.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.config import ensure_dirs, env, load_config  # noqa: E402
from agent.publish.instagram import InstagramClient  # noqa: E402
from agent.store import Store  # noqa: E402


def main() -> int:
    ok, bad = [], []
    cfg = load_config()
    ensure_dirs(cfg)

    # ffmpeg
    try:
        from agent.video.ffmpeg import ffmpeg_bin, ffmpeg_version

        ok.append(f"ffmpeg: {ffmpeg_version()[:60]}")
        ok.append(f"مسیر: {ffmpeg_bin()}")
    except Exception as exc:  # noqa: BLE001
        bad.append(f"ffmpeg: {exc}")

    # فونت
    from agent.fonts import resolve_font

    font = resolve_font("bold")
    (ok if font else bad).append(f"فونت فارسی: {font or 'پیدا نشد'}")

    # گویندگی
    try:
        import edge_tts  # type: ignore  # noqa: F401

        ok.append(f"edge-tts نصب است (گویندهٔ پیش‌فرض: {cfg.video.voice})")
    except ImportError:
        bad.append("edge-tts نصب نیست → pip install edge-tts")

    # دیتابیس
    try:
        store = Store(cfg)
        ok.append(f"دیتابیس: {store.db_path} ({sum(store.stats().values())} پست)")
    except Exception as exc:  # noqa: BLE001
        bad.append(f"دیتابیس: {exc}")

    # کلیدهای محتوا
    for key, label in (("GEMINI_API_KEY", "Gemini"), ("OPENAI_API_KEY", "OpenAI")):
        if env(key):
            ok.append(f"کلید {label} تنظیم شده است")

    # آپلودر
    uploader = (cfg.publish.uploader or env("UPLOADER", "uguu")).lower()
    if uploader in ("s3", "r2"):
        (ok if env("S3_BUCKET") else bad).append(
            f"آپلودر S3: باکت «{env('S3_BUCKET') or 'خالی'}»"
        )
    elif uploader == "local":
        (ok if env("PUBLIC_BASE_URL") else bad).append(
            f"آپلودر local: {env('PUBLIC_BASE_URL') or 'PUBLIC_BASE_URL خالی است'}"
        )
    else:
        ok.append(f"آپلودر {uploader} (لینک موقت — برای تولید S3 بگذارید)")

    # اینستاگرام
    client = InstagramClient(cfg)
    if client.configured:
        try:
            me = client.me()
            ok.append(f"اینستاگرام: @{me.get('username')} ({me.get('account_type', '—')})")
        except Exception as exc:  # noqa: BLE001
            bad.append(f"اینستاگرام: توکن هست ولی تست ناموفق — {exc}")
    else:
        bad.append("اینستاگرام: IG_ACCESS_TOKEN / IG_USER_ID تنظیم نشده")

    print("\n=== پیش‌بررسی ایجنت اینستاگرام ===\n")
    for line in ok:
        print("✅", line)
    for line in bad:
        print("❌", line)
    print()
    if not bad:
        print("🎉 همه‌چیز آماده است. حالا: python -m agent.cli generate")
        return 0
    print("ابتدا موارد ❌ را برطرف کنید (راهنما: docs/instagram-setup.md و README.md).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
