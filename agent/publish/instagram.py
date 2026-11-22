"""انتشار در اینستاگرام از طریق Instagram Graph API (رسمی متا).

جریان کار (دو مرحله‌ای، مطابق مستندات):
    ۱) ساخت «کانتینر» رسانه:   POST /{ig-user-id}/media   با video_url عمومی
    ۲) انتظار تا آماده‌شدن:     GET  /{container-id}?fields=status_code  → FINISHED
    ۳) انتشار:                 POST /{ig-user-id}/media_publish  با creation_id

دو مسیر لاگین پشتیبانی می‌شود:
    instagram : graph.instagram.com  — فقط با اکانت حرفه‌ای اینستاگرام، بدون پیج فیسبوک
    facebook  : graph.facebook.com   — اکانت اینستاگرام وصل به پیج فیسبوک
"""
from __future__ import annotations

import time
from typing import Any, Optional

import requests

from ..config import Cfg, env

GRAPH_VERSION = "v23.0"
INSTAGRAM_HOST = "graph.instagram.com"
FACEBOOK_HOST = "graph.facebook.com"


class InstagramError(RuntimeError):
    pass


class InstagramClient:
    def __init__(self, cfg: Cfg | None = None, access_token: str | None = None,
                 user_id: str | None = None, login: str | None = None):
        self.login = (login or env("IG_LOGIN", "instagram")).lower()
        self.access_token = (access_token or env("IG_ACCESS_TOKEN")).strip()
        self.user_id = (user_id or env("IG_USER_ID")).strip()
        self.host = FACEBOOK_HOST if self.login == "facebook" else INSTAGRAM_HOST
        self.base = f"https://{self.host}/{GRAPH_VERSION}"
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})

    # ---------- بررسی پیکربندی ----------
    @property
    def configured(self) -> bool:
        return bool(self.access_token and self.user_id)

    def require_config(self) -> None:
        if not self.configured:
            raise InstagramError(
                "توکن یا آی‌دی اینستاگرام تنظیم نشده است. "
                "IG_ACCESS_TOKEN و IG_USER_ID را در فایل .env بگذارید "
                "(راهنمای کامل: docs/instagram-setup.md)."
            )

    # ---------- فراخوانی پایه ----------
    def _call(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        url = path if path.startswith("http") else f"{self.base}/{path.lstrip('/')}"
        payload = kwargs.pop("data", None) or kwargs.pop("json", None)
        for attempt in range(1, 4):
            response = self.session.request(method, url, data=payload, timeout=120)
            try:
                body = response.json()
            except ValueError:
                raise InstagramError(f"پاسخ نامعتبر از متا ({response.status_code}): {response.text[:300]}")
            if response.status_code < 400 and "error" not in body:
                return body
            error = body.get("error", {}) or {}
            message = error.get("message", response.text[:300])
            code = error.get("code")
            subcode = error.get("error_subcode")
            # خطاهای گذرا را دوباره تلاش کن
            transient = response.status_code >= 500 or subcode == 2207003 or code in (1, 2, 4, 17)
            if transient and attempt < 3:
                time.sleep(5 * attempt)
                continue
            raise InstagramError(f"خطای متا [{code}/{subcode}] {message}")

    # ---------- اطلاعات اکانت ----------
    def me(self) -> dict[str, Any]:
        """اطلاعات اکانت + بررسی درست‌بودن توکن."""
        fields = "id,username,account_type,media_count" if self.login == "instagram" else "id,username"
        return self._get(f"{self.user_id}", {"fields": fields})

    def _get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        response = self.session.get(f"{self.base}/{path.lstrip('/')}", params=params, timeout=60)
        try:
            body = response.json()
        except ValueError:
            raise InstagramError(f"پاسخ نامعتبر از متا ({response.status_code})")
        if response.status_code < 400 and "error" not in body:
            return body
        error = (body.get("error") or {})
        raise InstagramError(f"خطای متا [{error.get('code')}] {error.get('message', body)}")

    # ---------- ریلز ----------
    def create_reel_container(self, video_url: str, caption: str,
                              share_to_feed: bool = True, cover_url: str = "") -> str:
        data: dict[str, Any] = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true" if share_to_feed else "false",
        }
        if cover_url:
            data["cover_url"] = cover_url
        body = self._call("POST", f"{self.user_id}/media", data=data)
        container_id = body.get("id")
        if not container_id:
            raise InstagramError(f"کانتینر ساخته نشد: {body}")
        return str(container_id)

    def container_status(self, container_id: str) -> str:
        body = self._get(container_id, {"fields": "status_code,status"})
        return str(body.get("status_code") or body.get("status") or "UNKNOWN")

    def wait_for_container(self, container_id: str, timeout: int = 600,
                           interval: int = 20) -> str:
        """تا آماده‌شدن ویدیو صبر می‌کند. برای ریلز معمولاً زیر چند دقیقه."""
        deadline = time.time() + timeout
        last = "UNKNOWN"
        while time.time() < deadline:
            last = self.container_status(container_id)
            if last == "FINISHED":
                return last
            if last in ("ERROR", "EXPIRED"):
                raise InstagramError(f"پردازش ویدیو در اینستاگرام شکست خورد: {last}")
            time.sleep(interval)
        raise InstagramError(f"آماده‌سازی کانتینر طول کشید (آخرین وضعیت: {last})")

    def publish_container(self, container_id: str) -> str:
        body = self._call("POST", f"{self.user_id}/media_publish",
                          data={"creation_id": container_id})
        media_id = body.get("id")
        if not media_id:
            raise InstagramError(f"انتشار انجام نشد: {body}")
        return str(media_id)

    def publish_reel(self, video_url: str, caption: str, share_to_feed: bool = True,
                     cover_url: str = "", wait_timeout: int = 600) -> dict[str, str]:
        container_id = self.create_reel_container(video_url, caption, share_to_feed, cover_url)
        self.wait_for_container(container_id, timeout=wait_timeout)
        media_id = self.publish_container(container_id)
        return {"container_id": container_id, "media_id": media_id}

    # ---------- سهمیهٔ انتشار ----------
    def publishing_limit(self) -> dict[str, Any]:
        """سهمیهٔ انتشار در ۲۴ ساعت گذشته را از متا می‌پرسد."""
        body = self._get(f"{self.user_id}/content_publishing_limit",
                         {"fields": "quota_usage,config"})
        data = body.get("data") or [{}]
        return data[0] if isinstance(data, list) and data else {}

    # ---------- کامنت ----------
    def comment(self, media_id: str, text: str) -> Optional[str]:
        """کامنت گذاشتن (برای هشتگ‌ها یا CTA)."""
        try:
            body = self._call("POST", f"{media_id}/comments", data={"message": text})
            return str(body.get("id", "")) or None
        except InstagramError:
            return None

    # ---------- توکن ----------
    def debug_token(self, token: str | None = None, app_id: str | None = None,
                    app_secret: str | None = None) -> dict[str, Any]:
        """اعتبار و انقضای توکن را چک می‌کند (نیاز به app access token)."""
        token = token or self.access_token
        app_id = app_id or env("FB_APP_ID")
        app_secret = app_secret or env("FB_APP_SECRET")
        if not (app_id and app_secret):
            raise InstagramError("برای debug_token باید FB_APP_ID و FB_APP_SECRET تنظیم شود.")
        response = requests.get(
            f"https://{FACEBOOK_HOST}/debug_token",
            params={"input_token": token, "access_token": f"{app_id}|{app_secret}"},
            timeout=30,
        )
        return response.json().get("data", {})

    def refresh_long_lived_token(self) -> str:
        """تمدید توکن بلندمدت اینستاگرام (قبل از ۶۰ روز، هر موقع)."""
        if self.login != "instagram":
            raise InstagramError("این عملیات فقط برای IG_LOGIN=instagram است.")
        response = requests.get(
            f"https://{INSTAGRAM_HOST}/refresh_access_token",
            params={"grant_type": "ig_refresh_token", "access_token": self.access_token},
            timeout=30,
        )
        body = response.json()
        if "access_token" not in body:
            raise InstagramError(f"تمدید توکن ناموفق بود: {body}")
        return body["access_token"]
