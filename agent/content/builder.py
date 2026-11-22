"""ساخت پیش‌نویس کامل: انتخاب ارائه‌دهنده، اعتبارسنجی، تولید تصویرها."""
from __future__ import annotations

from pathlib import Path

from ..config import env
from ..notify import get_logger
from .base import Draft, DraftScene
from .images import generate_image

log = get_logger("builder")


def _resolve_text_provider(cfg) -> str:
    requested = (cfg.content.text_provider or "auto").lower()
    if requested != "auto":
        return requested
    if env("GEMINI_API_KEY"):
        return "gemini"
    if env("OPENAI_API_KEY"):
        return "openai"
    return "offline"


def build_draft(cfg, topic: str | None = None, avoid: list[str] | None = None) -> Draft:
    """پیش‌نویس می‌سازد؛ اگر ارائه‌دهندهٔ انتخابی خطا داد به حالت آفلاین برمی‌گردد."""
    provider = _resolve_text_provider(cfg)
    draft: Draft | None = None

    if provider in ("gemini", "openai"):
        try:
            if provider == "gemini":
                from .gemini_provider import GeminiProvider

                draft = GeminiProvider(cfg).build(topic, avoid)
            else:
                from .openai_provider import OpenAIProvider

                draft = OpenAIProvider(cfg).build(topic, avoid)
        except Exception as exc:  # noqa: BLE001
            log.warning("تولید متن با %s ناموفق بود (%s) — استفاده از قالب آفلاین.", provider, exc)

    if draft is None:
        from .offline import OfflineProvider

        draft = OfflineProvider(cfg).build(topic, avoid)

    problems = draft.validate()
    if problems:
        log.warning("پیش‌نویس ایراد داشت (%s) — بازسازی با قالب آفلاین.", "؛ ".join(problems))
        from .offline import OfflineProvider

        draft = OfflineProvider(cfg).build(topic, avoid)

    draft.caption = _sanitize(draft.caption, cfg)
    draft.hashtags = _clean_hashtags(draft.hashtags, cfg, draft.topic)
    return draft


def _sanitize(text: str, cfg) -> str:
    """حذف عبارت‌های ممنوع و تمیزکاری کپشن."""
    out = text or ""
    for bad in (cfg.brand.forbidden or []):
        if bad:
            out = out.replace(bad, "")
    lines = [ln.rstrip() for ln in out.splitlines()]
    cleaned: list[str] = []
    for line in lines:
        if line.strip() or (cleaned and cleaned[-1].strip()):
            cleaned.append(line)
    return "\n".join(cleaned).strip()


def _topic_hashtag(topic: str, max_len: int = 30) -> str:
    """هشتگ ساخته‌شده از موضوع، بدون بریدن وسط کلمه."""
    words, out = topic.replace("‌", " ").split(), ""
    for word in words:
        candidate = f"{out}_{word}" if out else word
        if len(candidate) > max_len:
            break
        out = candidate
    return f"#{out.strip('_')}" if out else ""


def _clean_hashtags(tags: list[str], cfg, topic: str) -> list[str]:
    from ..rtl import join_hashtags

    base = list(cfg.brand.hashtags_base or [])
    extra = [_topic_hashtag(topic)] if topic else []
    joined = join_hashtags(base + list(tags or []) + extra)
    return joined.split(" ")[:12] if joined else []


def generate_images(draft: Draft, cfg, out_dir: Path) -> Draft:
    """برای هر صحنه یک تصویر ۹:۱۶ می‌سازد و مسیرش را در صحنه می‌گذارد."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, scene in enumerate(draft.scenes):
        target = out_dir / f"scene_{i + 1:02d}.jpg"
        prompt = scene.image_prompt or f"{draft.topic} — {scene.text}"
        if not prompt.lower().strip().endswith("no text"):
            prompt = f"{prompt}. Vertical 9:16, cinematic, no text, no letters, no watermark."
        log.info("تصویر صحنهٔ %s/%s ...", i + 1, len(draft.scenes))
        generate_image(prompt, target, cfg, index=i)
        scene.image_path = str(target)
    return draft
