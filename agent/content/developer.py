"""تبدیل پیش‌نویس به ScheduledPost و ثبت آن در دیتابیس."""
from __future__ import annotations

from pathlib import Path

from ..store import Scene, ScheduledPost, Store
from .base import Draft


def draft_to_post(draft: Draft, cfg, video_path: str = "", status: str = "draft") -> ScheduledPost:
    scenes = [
        Scene(index=i, text=s.text, narration=s.narration, image_prompt=s.image_prompt,
              image_path=s.image_path)
        for i, s in enumerate(draft.scenes)
    ]
    return ScheduledPost(
        status=status,
        mode=cfg.publish.mode,
        topic=draft.topic,
        title=draft.title,
        caption=draft.caption,
        hashtags=list(draft.hashtags or []),
        scenes=scenes,
        video_path=video_path,
        meta={"provider": draft.provider, **(draft.meta or {})},
    )


def save_post(post: ScheduledPost, cfg, store: Store | None = None,
              out_dir: Path | None = None) -> ScheduledPost:
    """پست را در SQLite و در فایل JSON کنار ویدیو ذخیره می‌کند."""
    store = store or Store(cfg)
    store.save(post)
    out_dir = Path(out_dir) if out_dir else cfg.get_path("out") / post.id
    try:
        post.save_json(out_dir / "post.json")
    except Exception:  # noqa: BLE001
        pass
    return post
