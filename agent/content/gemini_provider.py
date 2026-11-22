"""ارائه‌دهندهٔ محتوا با Google Gemini (متن + تصویر).

معماری مدل از SDK رسمی google-genai استفاده می‌کند و سه سطح پشتیبان دارد تا
با تغییر نام مدل‌ها نشکند.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import env
from .base import Draft, DraftScene
from .prompt import DRAFT_SCHEMA, build_system_prompt, build_user_prompt

TEXT_MODELS = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash"]
IMAGE_MODELS = ["gemini-2.5-flash-image", "gemini-3.1-flash-image", "gemini-2.5-flash-image-preview"]


class GeminiError(RuntimeError):
    pass


def _client():
    try:
        from google import genai  # type: ignore
    except ImportError as exc:
        raise GeminiError(
            "پکیج google-genai نصب نیست. اجرا کن: pip install google-genai"
        ) from exc
    key = env("GEMINI_API_KEY")
    if not key:
        raise GeminiError("GEMINI_API_KEY در فایل .env تنظیم نشده است.")
    return genai.Client(api_key=key)


def _is_model_error(exc: Exception) -> bool:
    text = str(exc)
    return "NOT_FOUND" in text or "not found" in text.lower() or "not supported" in text.lower()


class GeminiProvider:
    name = "gemini"

    def __init__(self, cfg):
        self.cfg = cfg

    # ---------- متن ----------
    def build(self, topic: str | None = None, avoid: list[str] | None = None) -> Draft:
        from google.genai import types  # type: ignore

        client = _client()
        models = [self.cfg.content.model_text] if self.cfg.content.model_text else TEXT_MODELS
        contents = (
            build_system_prompt(self.cfg) + "\n\n" + build_user_prompt(self.cfg, topic, avoid)
        )

        last_error: Exception | None = None
        for model in [m for m in models if m]:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=DRAFT_SCHEMA,
                        temperature=0.95,
                    ),
                )
                return self._parse(response.text or "", model)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if not _is_model_error(exc):
                    break
        raise GeminiError(f"تولید متن با Gemini ناموفق بود: {last_error}")

    def _parse(self, raw: str, model: str) -> Draft:
        import json

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            raw = raw[4:] if raw.lower().startswith("json") else raw
        try:
            data: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GeminiError(f"پاسخ مدل JSON معتبر نبود: {exc}") from exc

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
                response = client.models.generate_content(model=model, contents=prompt)
                for part in getattr(response, "parts", []) or []:
                    inline = getattr(part, "inline_data", None)
                    if inline is not None and getattr(inline, "data", None):
                        out_path.write_bytes(inline.data)
                        return out_path
                raise GeminiError("پاسخ مدل تصویری نداشت.")
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if not _is_model_error(exc):
                    break
        raise GeminiError(f"تولید تصویر با Gemini ناموفق بود: {last_error}")
