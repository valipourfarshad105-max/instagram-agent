"""زمان‌بندی خودکار (APScheduler): تولید و انتشار طبق config.yaml.

منطق کار:
- در هر «اسلات» زمانی از config.publish.schedule:
    * محتوای جدید تولید می‌شود (اگر تا آن لحظه پست آمادهٔ جدیدی نباشد).
    * در حالت auto، بلافاصله منتشر می‌شود.
    * در حالت approve، پیش‌نویس در داشبورد می‌ماند و تا شما تأیید نکنید منتشر نمی‌شود.
- یک کار روزانه هم پست‌های تأییدشدهٔ باقی‌مانده در صف را منتشر می‌کند
  (اگر خودتان بعد از زمان‌بندی تأیید کردید).
"""
from __future__ import annotations

import signal

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import Cfg, load_config
from .notify import get_logger, telegram_send
from .pipeline import produce, publish_approved, publish_post
from .store import Store

log = get_logger("scheduler")

DAY_MAP = {"mon": "mon", "tue": "tue", "wed": "wed", "thu": "thu",
           "fri": "fri", "sat": "sat", "sun": "sun"}


def _slot_job(cfg: Cfg, store: Store, slot: str) -> None:
    log.info("⏰ اسلات زمان‌بندی %s فعال شد.", slot)
    try:
        if cfg.publish.mode == "approve":
            ready = [p for p in store.list(status="approved", limit=5)]
            if ready:
                log.info("%s پست تأییدشده در صف است؛ منتشر می‌شوند.", len(ready))
                publish_approved(cfg, store)
        post = produce(cfg, store)
        log.info("پست %s آماده شد (%s).", post.id, post.status)
        if cfg.publish.mode == "auto" and post.status == "approved":
            publish_post(cfg, store, post, approve_first=False)
    except Exception as exc:  # noqa: BLE001
        log.exception("خطا در اجرای اسلات %s", slot)
        telegram_send(f"⚠️ خطا در اسلات زمان‌بندی {slot}: {str(exc)[:300]}")


def _queue_job(cfg: Cfg, store: Store) -> None:
    """هر ۱۵ دقیقه: اگر پست تأییدشده‌ای در صف ماند، منتشرش کن."""
    try:
        publish_approved(cfg, store)
    except Exception as exc:  # noqa: BLE001
        log.warning("انتشار صف ناموفق: %s", exc)


def _token_job() -> None:
    """هر ۳۰ روز: توکن بلندمدت اینستاگرام را تمدید کن."""
    from .config import env
    from .publish.instagram import InstagramClient

    try:
        client = InstagramClient()
        if not client.configured:
            return
        new_token = client.refresh_long_lived_token()
        log.info("توکن اینستاگرام تمدید شد. مقدار جدید را در .env بگذارید:")
        log.info("IG_ACCESS_TOKEN=%s", new_token)
        telegram_send("🔑 توکن اینستاگرام تمدید شد؛ مقدار جدید در لاگ سرور است.")
    except Exception as exc:  # noqa: BLE001
        log.warning("تمدید توکن ناموفق بود: %s", exc)


def build_scheduler(cfg: Cfg | None = None) -> BlockingScheduler:
    cfg = cfg or load_config()
    store = Store(cfg)
    scheduler = BlockingScheduler(timezone=cfg.publish.timezone)

    days = ",".join(DAY_MAP.get(str(d).lower()[:3], "mon") for d in cfg.publish.days)
    for slot in cfg.publish.schedule:
        hour, minute = (str(slot).split(":") + ["0"])[:2]
        scheduler.add_job(
            _slot_job, CronTrigger(day_of_week=days, hour=int(hour), minute=int(minute),
                                   timezone=cfg.publish.timezone),
            args=[cfg, store, slot], id=f"slot_{slot}", replace_existing=True,
            misfire_grace_time=3600, coalesce=True,
        )
        log.info("اسلات ثبت شد: روزهای %s ساعت %s (%s)", days, slot, cfg.publish.timezone)

    scheduler.add_job(
        _queue_job, "interval", minutes=15, args=[cfg, store],
        id="queue", replace_existing=True, coalesce=True,
    )
    scheduler.add_job(
        _token_job, "interval", days=30, id="token_refresh", replace_existing=True,
    )
    return scheduler


def run_scheduler(cfg: Cfg | None = None) -> None:
    cfg = cfg or load_config()
    mode = "خودکار" if cfg.publish.mode == "auto" else "تأیید دستی"
    log.info("زمان‌بند ایجنت شروع شد | حالت: %s | زمان: %s", mode, cfg.publish.timezone)
    log.info("ساعت‌های اجرا: %s | روزها: %s", "، ".join(cfg.publish.schedule), "، ".join(cfg.publish.days))

    scheduler = build_scheduler(cfg)
    stopping = {"flag": False}

    def _stop(*_args):
        stopping["flag"] = True
        log.info("در حال توقف زمان‌بند ...")
        scheduler.shutdown(wait=False)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
    log.info("زمان‌بند متوقف شد.")
