"""خط فرمان ایجنت اینستاگرام.

نمونه‌ها:
    python -m agent.cli init            # بررسی پیش‌نیازها و ساخت پوشه‌ها
    python -m agent.cli doctor          # چک‌لیست کامل اتصال‌ها
    python -m agent.cli generate        # ساخت یک پست (متن + تصویر + ویدیو)
    python -m agent.cli list            # فهرست پست‌ها
    python -m agent.cli approve <id>    # تأیید پیش‌نویس
    python -m agent.cli publish <id>    # انتشار در اینستاگرام
    python -m agent.cli dashboard       # داشبورد تأیید در مرورگر
    python -m agent.cli schedule        # اجرای زمان‌بند خودکار
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ROOT, ensure_dirs, env, load_config
from .notify import get_logger
from .pipeline import approve, produce, publish_approved, publish_post, reject
from .store import Store

log = get_logger("cli")


# ─────────────────────────────── دستورها ───────────────────────────────
def cmd_init(args) -> int:
    cfg = load_config()
    ensure_dirs(cfg)
    log.info("پوشه‌ها آماده شد: %s ، %s", cfg.get_path("out"), cfg.get_path("data"))
    if not (ROOT / ".env").exists() and (ROOT / ".env.example").exists():
        (ROOT / ".env").write_text((ROOT / ".env.example").read_text(encoding="utf-8"),
                                   encoding="utf-8")
        log.info("فایل .env از نمونه ساخته شد؛ کلیدها را داخلش بگذارید.")
    from .video.ffmpeg import ffmpeg_bin, ffmpeg_version

    log.info("ffmpeg: %s", ffmpeg_version())
    log.info("مسیر ffmpeg: %s", ffmpeg_bin())
    from .fonts import resolve_font

    log.info("فونت فارسی: %s", resolve_font("bold"))
    log.info("همه‌چیز آماده است. برای بررسی اتصال‌ها: python -m agent.cli doctor")
    return 0


def cmd_doctor(args) -> int:
    cfg = load_config()
    ok, warn = [], []

    from .video.ffmpeg import ffmpeg_bin

    try:
        ok.append(f"ffmpeg پیدا شد: {Path(ffmpeg_bin()).name}")
    except Exception as exc:  # noqa: BLE001
        warn.append(f"ffmpeg: {exc}")

    from .fonts import resolve_font

    font = resolve_font("bold")
    (ok if font else warn).append(f"فونت فارسی: {font or 'پیدا نشد'}")

    # تولید محتوا
    if env("GEMINI_API_KEY"):
        ok.append("کلید Gemini تنظیم شده است.")
    elif env("OPENAI_API_KEY"):
        ok.append("کلید OpenAI تنظیم شده است.")
    else:
        warn.append("هیچ کلید هوش مصنوعی‌ای وجود ندارد؛ ایجنت در حالت قالب آفلاین کار می‌کند.")

    # آپلودر
    uploader = (cfg.publish.uploader or env("UPLOADER", "uguu")).lower()
    if uploader in ("uguu", "litterbox", "catbox"):
        warn.append(f"آپلودر {uploader} بدون کلید کار می‌کند ولی لینک موقت است "
                    "(برای استفادهٔ واقعی S3/R2 را تنظیم کنید).")
    elif uploader in ("s3", "r2"):
        if env("S3_BUCKET"):
            ok.append(f"آپلودر {uploader} با باکت «{env('S3_BUCKET')}» تنظیم شده است.")
        else:
            warn.append("S3 انتخاب شده ولی S3_BUCKET خالی است.")
    elif uploader == "local" and not env("PUBLIC_BASE_URL"):
        warn.append("UPLOADER=local است ولی PUBLIC_BASE_URL خالی است.")

    # اینستاگرام
    from .publish.instagram import InstagramClient

    client = InstagramClient(cfg)
    if client.configured:
        try:
            me = client.me()
            ok.append(f"اتصال اینستاگرام درست است → @{me.get('username', '?')} "
                      f"(id: {me.get('id')}، نوع: {me.get('account_type', client.login)})")
        except Exception as exc:  # noqa: BLE001
            warn.append(f"توکن اینستاگرام تنظیم شده ولی تست ناموفق بود: {exc}")
    else:
        warn.append("IG_ACCESS_TOKEN / IG_USER_ID تنظیم نشده — انتشار انجام نمی‌شود "
                    "(راهنما: docs/instagram-setup.md).")

    print("\n✅ موارد سالم:")
    for line in ok:
        print("   ✅", line)
    print("\n⚠️ مواردی که باید تکمیل شوند:")
    for line in warn or ["   -"]:
        print("   ⚠️", line)
    print()
    return 0 if client.configured else 1


def cmd_generate(args) -> int:
    cfg = load_config()
    store = Store(cfg)
    count = max(1, args.count or cfg.content.ideas_per_run)
    for i in range(count):
        log.info("── ساخت پست %s از %s ──", i + 1, count)
        post = produce(cfg, store, topic=args.topic, publish_now=args.publish)
        log.info("شناسهٔ پست: %s | وضعیت: %s | ویدیو: %s", post.id, post.status, post.video_path)
    return 0


def cmd_list(args) -> int:
    cfg = load_config()
    store = Store(cfg)
    stats = store.stats()
    print("\n📊 شمارش وضعیت‌ها:")
    for key, value in stats.items():
        if value:
            print(f"   {key:12s} {value}")
    print()
    for post in store.list(status=args.status, limit=args.limit):
        print(f"[{post.status:10s}] {post.id}  {post.created_at[:16]}  {post.topic[:42]}")
    print()
    return 0


def cmd_show(args) -> int:
    cfg = load_config()
    post = Store(cfg).get(args.post_id)
    if not post:
        print("پست پیدا نشد.")
        return 1
    print(f"\nشناسه: {post.id}\nوضعیت: {post.status}\nموضوع: {post.topic}\nعنوان: {post.title}")
    print(f"ویدیو: {post.video_path or '-'}\nلینک: {post.video_url or '-'}\nmedia_id: {post.ig_media_id or '-'}")
    print(f"\nکپشن:\n{post.caption}\n\nهشتگ‌ها: {' '.join(post.hashtags)}\n")
    for i, scene in enumerate(post.scenes, 1):
        print(f"  صحنه {i}: [{scene.text}]")
        print(f"           گفتار: {scene.narration}")
    print()
    return 0


def cmd_approve(args) -> int:
    cfg = load_config()
    post = approve(cfg, Store(cfg), args.post_id)
    print(f"✅ پست {post.id} تأیید شد.")
    return 0


def cmd_reject(args) -> int:
    cfg = load_config()
    reject(cfg, Store(cfg), args.post_id)
    print("پست رد شد.")
    return 0


def cmd_publish(args) -> int:
    cfg = load_config()
    store = Store(cfg)
    if args.all:
        published = publish_approved(cfg, store)
        print(f"✅ {len(published)} پست منتشر شد.")
        return 0
    if not args.post_id:
        print("شناسهٔ پست لازم است (یا از --all استفاده کنید).")
        return 2
    post = publish_post(cfg, store, args.post_id, approve_first=not args.force)
    print(f"🚀 منتشر شد. media_id: {post.ig_media_id}")
    return 0


def cmd_rebuild(args) -> int:
    cfg = load_config()
    store = Store(cfg)
    post = store.get(args.post_id)
    if not post:
        print("پست پیدا نشد.")
        return 1
    from .video.reels import build_reel

    video = build_reel(post, cfg, cfg.get_path("out") / post.id, keep_temp=args.keep_temp)
    store.update(post.id, video_path=str(video), cover_path=post.cover_path)
    print(f"🎬 ویدیو بازسازی شد: {video}")
    return 0


def cmd_schedule(args) -> int:
    from .scheduler import run_scheduler

    run_scheduler(load_config())
    return 0


def cmd_dashboard(args) -> int:
    from .dashboard import run_dashboard

    run_dashboard(load_config())
    return 0


def cmd_ig_check(args) -> int:
    from .publish.instagram import InstagramClient

    client = InstagramClient(load_config())
    client.require_config()
    me = client.me()
    print("\n📷 اتصال اینستاگرام:")
    for key, value in me.items():
        print(f"   {key}: {value}")
    print()
    return 0


def cmd_limit(args) -> int:
    """سهمیهٔ انتشار روزانهٔ اکانت را از متا می‌پرسد."""
    from .publish.instagram import InstagramClient

    client = InstagramClient(load_config())
    client.require_config()
    data = client.publishing_limit()
    quota = data.get("quota_usage", "?")
    config = (data.get("config") or {})
    total = config.get("quota_total", "?")
    print(f"\n📊 انتشار در ۲۴ ساعت گذشته: {quota} از {total}\n")
    return 0


def cmd_refresh_token(args) -> int:
    from .publish.instagram import InstagramClient

    client = InstagramClient(load_config())
    client.require_config()
    token = client.refresh_long_lived_token()
    print("\n🔑 توکن جدید (در .env جای‌گذاری کنید):\n")
    print(f"IG_ACCESS_TOKEN={token}\n")
    return 0


def cmd_upload_test(args) -> int:
    """تست میزبان آپلود با یک فایل کوچک."""
    cfg = load_config()
    tmp = cfg.get_path("data") / "upload_test.mp4"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    from .video.ffmpeg import run, silence_wav

    wav = silence_wav(cfg.get_path("data") / "silence.wav", 1.0)
    run(["-f", "lavfi", "-i", "color=c=black:s=320x568:d=1:r=30", "-i", str(wav),
         "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(tmp)])
    from .publish.uploader import upload

    url = upload(tmp, args.uploader or cfg.publish.uploader or None, cfg)
    print(f"\n✅ آپلود موفق. آدرس عمومی:\n{url}\n")
    return 0


# ─────────────────────────────── ورودی ───────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent", description="ایجنت تولید و انتشار خودکار ریلز اینستاگرام",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="بررسی پیش‌نیازها و ساخت پوشه‌ها").set_defaults(func=cmd_init)
    sub.add_parser("doctor", help="چک‌لیست اتصال‌ها و کلیدها").set_defaults(func=cmd_doctor)

    p_gen = sub.add_parser("generate", help="ساخت پست جدید (متن، تصویر، ویدیو)")
    p_gen.add_argument("--topic", help="موضوع دلخواه (پیش‌فرض: خودکار)")
    p_gen.add_argument("--count", type=int, default=0, help="چند پست بسازد")
    p_gen.add_argument("--publish", action="store_true", help="بعد از ساخت، بلافاصله منتشر کن")
    p_gen.set_defaults(func=cmd_generate)

    p_list = sub.add_parser("list", help="فهرست پست‌ها")
    p_list.add_argument("--status", choices=["draft", "generating", "pending", "approved",
                                             "publishing", "published", "failed", "rejected"])
    p_list.add_argument("--limit", type=int, default=20)
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="نمایش جزئیات یک پست")
    p_show.add_argument("post_id")
    p_show.set_defaults(func=cmd_show)

    p_ok = sub.add_parser("approve", help="تأیید پیش‌نویس")
    p_ok.add_argument("post_id")
    p_ok.set_defaults(func=cmd_approve)

    p_no = sub.add_parser("reject", help="رد پیش‌نویس")
    p_no.add_argument("post_id")
    p_no.set_defaults(func=cmd_reject)

    p_pub = sub.add_parser("publish", help="انتشار در اینستاگرام")
    p_pub.add_argument("post_id", nargs="?")
    p_pub.add_argument("--all", action="store_true", help="همهٔ پست‌های تأییدشده")
    p_pub.add_argument("--force", action="store_true", help="بدون نیاز به تأیید قبلی")
    p_pub.set_defaults(func=cmd_publish)

    p_rb = sub.add_parser("rebuild-video", help="ساخت مجدد ویدیوی یک پست")
    p_rb.add_argument("post_id")
    p_rb.add_argument("--keep-temp", action="store_true", help="نگه‌داشتن فریم‌ها و کلیپ‌های میانی")
    p_rb.set_defaults(func=cmd_rebuild)

    sub.add_parser("schedule", help="اجرای زمان‌بند خودکار").set_defaults(func=cmd_schedule)
    sub.add_parser("dashboard", help="داشبورد تأیید").set_defaults(func=cmd_dashboard)
    sub.add_parser("ig-check", help="تست اتصال اینستاگرام").set_defaults(func=cmd_ig_check)
    sub.add_parser("publish-limit", help="سهمیهٔ انتشار ۲۴ ساعت گذشته").set_defaults(func=cmd_limit)
    sub.add_parser("refresh-token", help="تمدید توکن بلندمدت اینستاگرام").set_defaults(func=cmd_refresh_token)

    p_up = sub.add_parser("upload-test", help="تست میزبان آپلود ویدیو")
    p_up.add_argument("--uploader", help="uguu | litterbox | catbox | s3 | local")
    p_up.set_defaults(func=cmd_upload_test)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
