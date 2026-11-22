"""ساختار دادهٔ پیش‌نویس (خروجی مشترک همهٔ ارائه‌دهنده‌های محتوا)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DraftScene:
    text: str          # متن روی تصویر (کوتاه: ۲ تا ۶ کلمه)
    narration: str     # جمله‌ای که گوینده می‌خواند (۱۵ تا ۲۵ کلمه)
    image_prompt: str = ""
    image_path: str = ""


@dataclass
class Draft:
    topic: str
    title: str
    scenes: list[DraftScene] = field(default_factory=list)
    caption: str = ""
    hashtags: list[str] = field(default_factory=list)
    provider: str = "offline"
    meta: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """ایرادهای ساختاری را برمی‌گرداند (خالی = سالم)."""
        problems: list[str] = []
        if not self.topic.strip():
            problems.append("موضوع خالی است")
        if len(self.scenes) < 3:
            problems.append(f"تعداد صحنه‌ها کم است ({len(self.scenes)})")
        for i, scene in enumerate(self.scenes, 1):
            if not scene.text.strip():
                problems.append(f"متن صحنهٔ {i} خالی است")
            if not scene.narration.strip():
                problems.append(f"گفتار صحنهٔ {i} خالی است")
        if not self.caption.strip():
            problems.append("کپشن خالی است")
        if len(self.caption) > 2100:
            problems.append(f"کپشن طولانی است ({len(self.caption)} کاراکتر)")
        return problems

    def total_narration_words(self) -> int:
        return sum(len(s.narration.split()) for s in self.scenes)
