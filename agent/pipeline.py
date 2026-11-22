"""خط تولید ایجنت: ایده → متن → تصویر → ویدیو → (تأیید) → آپلود → انتشار."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import Cfg
from .content.builder import build_draft, generate_images
from .content.developer import draft_to_post, save_post
from .notify import get_logger, notify_error, notify_new_draft, notify_published
from .publish.instagram import InstagramClient, InstagramError
from .publish.uploader import UploadError, upload
from .store import ScheduledPost, Store
from .video.reels import build_reel

log = get_logger("pipeline")


def local_now(cfg: Cfg) -> datetime:
    return datetime.now(ZoneInfo(cfg.publish.timezone))


# ─────────────────────────────── خط تولید ───────────────────────────────
def produce(cfg: Cfg, store: Store | None = None, topic: str | None = None,
            publish_now: bool = False) -> ScheduledPost:
    """یک پیش‌نویس کامل (شامل ویدیو) می‌سازد و در صف تأیید/انتشار می‌گذارد."""
    store = store or Store(cfg)
    post = ScheduledPost(status="generating", mode=cfg.publish.mode, topic=topic or "")

    try:
        # ۱) متن
        log.info("تولید ایده و متن ...")
        draft = build_draft(cfg, topic=topic, avoid=store.recent_topics())
        post = draft_to_post(draft, cfg, status="generating")
        work_dir = cfg.get_path("out") / post.id
        work_dir.mkdir(parents=True, exist_ok=True)
        store.save(post)
        log.info("موضوع: %s | ارائه‌دهنده: %s", draft.topic, draft.provider)

        # ۲) تصویرها
        log.info("ساخت %s تصویر ...", len(draft.scenes))
        generate_images(draft, cfg, work_dir / "images")
        post.scenes = draft_to_post(draft, cfg).scenes
        store.save(post)
        work_dir = cfg.get_path("out") / post.id
        work_dir.mkdir(parents=True, exist_ok=True)

        # ۳) ویدیو
        log.info("مونتاژ ویدیو (گویندگی + تصاویر) ...")
        video = build_reel(post, cfg, work_dir)
        post.video_path = str(video)
        post.status = "pending" if cfg.publish.mode == "approve" else "approved"
        store.save(post)
        store.update(post.id, meta=post.meta)
        post.save_json(work_dir / "post.json")  # نسخهٔ خوانا کنار ویدیو

        log.info("ویدیو آماده شد: %s (%.1f مگابایت)",
                 video, video.stat().st_size / 1_048_576)

        if cfg.publish.mode == "approve":
            notify_new_draft(post)
        if publish_now or cfg.publish.mode == "auto":
            return publish_post(cfg, store, post)
        return post

    except Exception as exc:  # noqa: BLE001
        log.exception("خطا در تولید محتوا")
        store.update(post.id, status="failed", error=str(exc)[:900])
        notify_error(post, str(exc))
        raise


# ─────────────────────────────── انتشار ───────────────────────────────
def publish_post(cfg: Cfg, store: Store | None = None, post: ScheduledPost | str | None = None,
                 approve_first: bool = True) -> ScheduledPost:
    """پست را آپلود و در اینستاگرام منتشر می‌کند (با تلاش مجدد).

    approve_first=True  → اگر پست در حالت «در انتظار تأیید» باشد منتشر نمی‌شود.
    approve_first=False → انتشار فوری، حتی بدون تأیید.
    """
    store = store or Store(cfg)
    if isinstance(post, str):
        post = store.get(post)
    if post is None:
        raise ValueError("پست پیدا نشد")
    if not post.video_path or not Path(post.video_path).exists():
        raise FileNotFoundError(f"فایل ویدیو پیدا نشد: {post.video_path}")

    if approve_first and post.status in ("pending", "draft", "generating"):
        raise RuntimeError(
            f"این پست هنوز تأیید نشده است (وضعیت: {post.status}). "
            "اول با «approve» تأییدش کنید یا از --force استفاده کنید."
        )

    previous_status = post.status
    client = InstagramClient(cfg)
    try:
        client.require_config()
    except InstagramError as exc:
        # پیکربندی ناقص است؛ پست از صف حذف نمی‌شود و وضعیتش دست‌نخورده می‌ماند
        store.update(post.id, status=previous_status, error=str(exc)[:400])
        raise

    store.update(post.id, status="publishing", error="")

    attempts = max(1, int(cfg.publish.retry))
    last_error: Exception | None = None
    config_error = False

    for attempt in range(1, attempts + 1):
        try:
            # ۱) آپلود روی یک URL عمومی
            log.info("آپلود ویدیو روی میزبان عمومی (%s) ...", cfg.publish.uploader or "env")
            video_url = upload(post.video_path, cfg.publish.uploader or None, cfg)
            store.update(post.id, video_url=video_url)

            # ۲) کانتینر + انتشار
            log.info("ساخت کانتینر ریلز در اینستاگرام ...")
            result = client.publish_reel(
                video_url=video_url,
                caption=post.full_caption,
                share_to_feed=bool(cfg.publish.share_to_feed),
            )

            # ۳) اولین کامنت (هشتگ‌ها) — اختیاری
            if cfg.publish.first_comment and post.hashtags:
                client.comment(result["media_id"], " ".join(post.hashtags))

            post.status = "published"
            post.published_at = datetime.now(timezone.utc).isoformat()
            post.ig_media_id = result["media_id"]
            post.video_url = video_url
            post.error = ""
            store.save(post)
            log.info("✅ منتشر شد! media_id=%s", result["media_id"])
            notify_published(post)
            return post

        except (UploadError, InstagramError, FileNotFoundError) as exc:
            last_error = exc
            log.warning("تلاش %s/%s ناموفق: %s", attempt, attempts, exc)
            if attempt < attempts and not _is_config_error(exc):
                time.sleep(min(60, 10 * attempt))
            else:
                break

    message = f"انتشار ناموفق ماند: {last_error}"
    final_status = previous_status if _is_config_error(last_error) else "failed"
    store.update(post.id, status=final_status, error=str(last_error)[:900])
    log.error(message)
    notify_error(post, message)
    raise RuntimeError(message)


def _is_config_error(error: Exception | None) -> bool:
    """خطاهایی که ریشه‌شان پیکربندی ناقص است (توکن/آی‌دی/S3) — پست در صف می‌ماند."""
    if isinstance(error, UploadError):
        return True
    text = str(error or "")
    return "تنظیم نشده" in text or "پیدا نشد" in text and "ویدیو" not in text


# ─────────────────────────────── کنترل صف ───────────────────────────────
def approve(cfg: Cfg, store: Store, post_id: str) -> ScheduledPost:
    post = store.get(post_id)
    if post is None:
        raise ValueError("پست پیدا نشد")
    post.status = "approved"
    store.save(post)
    log.info("پست %s تأیید شد و در صف انتشار است.", post_id)
    return post


def reject(cfg: Cfg, store: Store, post_id: str) -> ScheduledPost:
    post = store.get(post_id)
    if post is None:
        raise ValueError("پست پیدا نشد")
    post.status = "rejected"
    store.save(post)
    return post


def publish_approved(cfg: Cfg, store: Store | None = None) -> list[ScheduledPost]:
    """همهٔ پست‌های تأییدشده را (با رعایت سقف روزانه) منتشر می‌کند."""
    store = store or Store(cfg)
    published: list[ScheduledPost] = []
    if _daily_quota_reached(cfg, store):
        log.info("سقف انتشار روزانه پر شده است (%s پست).", cfg.publish.max_posts_per_day)
        return published
    for post in reversed(store.list(status="approved", limit=10)):
        if _daily_quota_reached(cfg, store):
            break
        try:
            published.append(publish_post(cfg, store, post))
        except Exception as exc:  # noqa: BLE001
            log.error("انتشار %s ناموفق بود: %s", post.id, exc)
    return published


def _daily_quota_reached(cfg: Cfg, store: Store) -> bool:
    local_midnight = local_now(cfg).replace(hour=0, minute=0, second=0, microsecond=0)
    since = local_midnight.astimezone(timezone.utc).isoformat()
    return store.count_since("published", since) >= int(cfg.publish.max_posts_per_day)


def cleanup_old_drafts(cfg: Cfg, store: Store, days: int = 30) -> int:
    """پست‌های رد/ناموفق قدیمی را پاک می‌کند (فقط رکورد دیتابیس، نه فایل‌های ویدیو)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    removed = 0
    for status in ("rejected", "failed"):
        for post in store.list(status=status, limit=200):
            if post.created_at < cutoff:
                store.update(post.id, status="rejected")
                removed += 1
    return removed
