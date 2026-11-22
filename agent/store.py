"""ذخیره‌سازی محلی: دیتابیس SQLite برای پست‌ها + فایل‌های JSON کنار هر ویدیو.

ScheduledPost = نشست اصلی کل سیستم (تولید → تأیید → انتشار → لاگ)
ساختار آن (JSON) در فایل کنار ویدیو هم ذخیره می‌شود تا داشبورد بی‌دیتابیس هم کار کند.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .config import Cfg, ensure_dirs

STATUSES = ("draft", "pending", "approved", "publishing", "published", "failed", "rejected")

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    scheduled_at TEXT,
    published_at TEXT,
    status TEXT NOT NULL,
    topic TEXT,
    title TEXT,
    caption TEXT,
    hashtags TEXT,          -- JSON array
    scenes TEXT,            -- JSON array (فقط متن، بدون دادهٔ حجیم)
    video_path TEXT,
    cover_path TEXT,
    video_url TEXT,
    ig_media_id TEXT,
    error TEXT,
    mode TEXT,
    meta TEXT,              -- JSON برای هر چیز اضافه
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at);
"""


@dataclass
class Scene:
    index: int
    text: str           # متن روی تصویر (کوتاه)
    narration: str      # چیزی که خوانده می‌شود
    image_prompt: str
    image_path: str = ""
    overlay: str = ""   # متن کمکی کوچک (اختیاری)


@dataclass
class ScheduledPost:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    scheduled_at: Optional[str] = None
    published_at: Optional[str] = None
    status: str = "draft"
    mode: str = "approve"
    topic: str = ""
    title: str = ""
    caption: str = ""
    hashtags: list[str] = field(default_factory=list)
    scenes: list[Scene] = field(default_factory=list)
    video_path: str = ""
    cover_path: str = ""
    video_url: str = ""
    ig_media_id: str = ""
    error: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    # ---------- تبدیل ----------
    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["scenes"] = [asdict(s) if not isinstance(s, dict) else s for s in self.scenes]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScheduledPost":
        data = dict(data or {})
        scenes = [Scene(**s) if isinstance(s, dict) else s for s in data.pop("scenes", []) or []]
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        clean = {k: v for k, v in data.items() if k in known}
        post = cls(**clean)
        post.scenes = scenes
        return post

    @property
    def full_caption(self) -> str:
        tags = " ".join(self.hashtags or [])
        return f"{self.caption}\n\n{tags}".strip()

    def save_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


class Store:
    def __init__(self, cfg: Cfg | None = None, db_path: str | Path | None = None):
        if db_path is None:
            if cfg is None:
                raise ValueError("cfg یا db_path لازم است")
            ensure_dirs(cfg)
            db_path = cfg.get_path("db")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    # ---------- نوشتن ----------
    def save(self, post: ScheduledPost) -> ScheduledPost:
        row = post.to_dict()
        payload = {
            "id": post.id,
            "created_at": post.created_at,
            "scheduled_at": post.scheduled_at,
            "published_at": post.published_at,
            "status": post.status,
            "topic": post.topic,
            "title": post.title,
            "caption": post.caption,
            "hashtags": json.dumps(post.hashtags, ensure_ascii=False),
            "scenes": json.dumps([asdict(s) for s in post.scenes], ensure_ascii=False),
            "video_path": post.video_path,
            "cover_path": post.cover_path,
            "video_url": post.video_url,
            "ig_media_id": post.ig_media_id,
            "error": post.error,
            "mode": post.mode,
            "meta": json.dumps(post.meta, ensure_ascii=False, default=str),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        cols = ", ".join(payload)
        marks = ", ".join(f":{c}" for c in payload)
        with self._connect() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO posts ({cols}) VALUES ({marks})", payload
            )
        return post

    def update(self, post_id: str, **fields) -> None:
        if not fields:
            return
        if "hashtags" in fields and not isinstance(fields["hashtags"], str):
            fields["hashtags"] = json.dumps(fields["hashtags"], ensure_ascii=False)
        if "scenes" in fields and not isinstance(fields["scenes"], str):
            fields["scenes"] = json.dumps(fields["scenes"], ensure_ascii=False, default=str)
        if "meta" in fields and not isinstance(fields["meta"], str):
            fields["meta"] = json.dumps(fields["meta"], ensure_ascii=False, default=str)
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        fields["id"] = post_id
        with self._connect() as conn:
            conn.execute(f"UPDATE posts SET {sets} WHERE id = :id", fields)

    def set_status(self, post_id: str, status: str, **extra) -> None:
        self.update(post_id, status=status, **extra)

    # ---------- خواندن ----------
    def get(self, post_id: str) -> ScheduledPost | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        return self._row_to_post(row) if row else None

    def list(self, status: str | None = None, limit: int = 100) -> list[ScheduledPost]:
        query = "SELECT * FROM posts"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_post(r) for r in rows]

    def count_since(self, status: str, since_iso: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM posts WHERE status = ? AND created_at >= ?",
                (status, since_iso),
            ).fetchone()
        return int(row["c"]) if row else 0

    def recent_topics(self, limit: int = 12) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT topic FROM posts WHERE topic != '' ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [r["topic"] for r in rows]

    def stats(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute("SELECT status, COUNT(*) c FROM posts GROUP BY status").fetchall()
        result = {s: 0 for s in STATUSES}
        result.update({r["status"]: r["c"] for r in rows})
        return result

    @staticmethod
    def _row_to_post(row: sqlite3.Row) -> ScheduledPost:
        data = dict(row)
        data["hashtags"] = json.loads(data.get("hashtags") or "[]")
        data["scenes"] = json.loads(data.get("scenes") or "[]")
        data["meta"] = json.loads(data.get("meta") or "{}")
        return ScheduledPost.from_dict(data)
