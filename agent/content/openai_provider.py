"""ارائه‌دهندهٔ محتوا با OpenAI (متن + تصویر)."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from ..config import env
from .base import Draft, DraftScene
from .prompt import build_system_prompt, build_user_prompt

TEXT_MODELS = ["gpt-5", "gpt-4.1", "gpt-4o"]
IMAGE_MODELS = ["gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini"]


class OpenAIError(RuntimeError):
    pass


def _client():
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as exc:
        raise OpenAIError("پکیج openai نصب نیست. اجرا کن: pip install openai") from exc
    key = env("OPENAI_API_KEY")
    if not key:
        raise OpenAIError("OPENAI_API_KEY در فایل .env تنظیم نشده است.")
    return OpenAI(api_key=key)


def _is_model_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "model" in text and ("not found" in text or "does not exist" in text or "unsupported" in text)


class OpenAIProvider:
    name = "openai"

    def __init__(self, cfg):
        self.cfg = cfg

    # ---------- متن ----------
    def build(self, topic: str | None = None, avoid: list[str] | None = None) -> Draft:
        client = _client()
        models = [self.cfg.content.model_text] if self.cfg.content.model_text else TEXT_MODELS
        messages = [
            {"role": "system", "content": build_system_prompt(self.cfg)},
            {"role": "user", "content": build_user_prompt(self.cfg, topic, avoid)},
        ]
        last_error: Exception | None = None
        for model in [m for m in models if m]:
            try:
                try:
                    response = client.chat.completions.create(
                        model=model, messages=messages,
                        response_format={"type": "json_object"}, temperature=0.95,
                    )
                except Exception as exc:  # noqa: BLE001  (مثلاً مدل‌هایی که json_object را قبول نمی‌کنند)
                    if _is_model_error(exc):
                        raise
                    response = client.chat.completions.create(
                        model=model, messages=messages, temperature=0.95
                    )
                raw = (response.choices[0].message.content or "").strip()
                return self._parse(raw, model)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if not _is_model_error(exc):
                    break
        raise OpenAIError(f"تولید متن با OpenAI ناموفق بود: {last_error}")

    def _parse(self, raw: str, model: str) -> Draft:
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            raw = raw[4:] if raw.lower().startswith("json") else raw
        try:
            data: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OpenAIError(f"پاسخ مدل JSON معتبر نبود: {exc}") from exc
        scenes = [
            DraftScene(
                text=str(s.get("text", "")).strip(),
                narration=str(s.get("narration", "")).strip(),
                image_prompt=str(s.get("image_prompt", "")).strip(),
            )
            for s in data.get("scenes", [])
        ]
        return Draft(
            topic=str(data.get("topic", "")).strip(),
            title=str(data.get("title", "")).strip(),
            scenes=scenes,
            caption=str(data.get("caption", "")).strip(),
            hashtags=[str(h).strip() for h in data.get("hashtags", []) if str(h).strip()],
            provider=f"{self.name}:{model}",
        )

    # ---------- تصویر ----------
    def image(self, prompt: str, out_path: Path) -> Path:
        client = _client()
        models = [self.cfg.content.model_image] if self.cfg.content.model_image else IMAGE_MODELS
        out_path.parent.mkdir(parents=True, exist_ok=True)
        last_error: Exception | None = None
        for model in [m for m in models if m]:
            try:
                response = client.images.generate(model=model, prompt=prompt, size="1024x1536")
                item = response.data[0]
                if getattr(item, "b64_json", None):
                    out_path.write_bytes(base64.b64decode(item.b64_json))
                    return out_path
                if getattr(item, "url", None):
                    import requests

                    out_path.write_bytes(requests.get(item.url, timeout=120).content)
                    return out_path
                raise OpenAIError("پاسخ مدل تصویری نداشت.")
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if not _is_model_error(exc):
                    break
        raise OpenAIError(f"تولید تصویر با OpenAI ناموفق بود: {last_error}")
