"""آپلود فایل ویدیو/تصویر روی یک URL عمومی.

اینستاگرام رسانه را خودش از روی URL دانلود می‌کند؛ پس فایل باید جایی عمومی
و سریع میزبانی شود. گزینه‌ها:

    uguu      : بدون کلید، فایل تا ~۳ ساعت می‌ماند  → فقط برای تست
    litterbox : بدون کلید، تا ۷۲ ساعت می‌ماند        → فقط برای تست
    catbox    : بدون کلید، دائمی                     → احتمال مسدودشدن دارد
    s3        : Cloudflare R2 یا AWS S3              → پیشنهاد برای استفادهٔ واقعی
    local     : از دامنهٔ PUBLIC_BASE_URL خودتان سرو می‌شود
"""
from __future__ import annotations

import time
from pathlib import Path

import requests

from ..config import Cfg, env


class UploadError(RuntimeError):
    pass


# ──────────────────────────────── بک‌اندها ────────────────────────────────
def upload_uguu(path: Path) -> str:
    with open(path, "rb") as fh:
        response = requests.post(
            "https://uguu.se/upload", files={"files[]": (path.name, fh, "video/mp4")},
            params={"output": "text"}, timeout=300,
        )
    text = response.text.strip()
    if response.status_code >= 400 or not text.startswith("http"):
        raise UploadError(f"uguu: {text[:200]}")
    return text.splitlines()[0]


def upload_litterbox(path: Path, hours: int = 72) -> str:
    with open(path, "rb") as fh:
        response = requests.post(
            "https://litterbox.catbox.moe/resources/internals/api.php",
            data={"reqtype": "fileupload", "time": f"{hours}h"},
            files={"fileToUpload": (path.name, fh, "video/mp4")}, timeout=600,
        )
    url = response.text.strip()
    if not url.startswith("http"):
        raise UploadError(f"litterbox: {url[:200]}")
    return url


def upload_catbox(path: Path) -> str:
    with open(path, "rb") as fh:
        response = requests.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": (path.name, fh, "video/mp4")}, timeout=600,
        )
    url = response.text.strip()
    if not url.startswith("http"):
        raise UploadError(f"catbox: {url[:200]}")
    return url


def upload_s3(path: Path) -> str:
    try:
        import boto3  # type: ignore
    except ImportError as exc:
        raise UploadError("برای UPLOADER=s3 باید pip install boto3 انجام شود.") from exc

    endpoint = env("S3_ENDPOINT_URL") or None
    bucket = env("S3_BUCKET")
    public_base = (env("S3_PUBLIC_BASE_URL") or "").rstrip("/")
    if not bucket:
        raise UploadError("S3_BUCKET تنظیم نشده است.")
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=env("S3_REGION", "auto"),
        aws_access_key_id=env("S3_ACCESS_KEY"),
        aws_secret_access_key=env("S3_SECRET_KEY"),
    )
    key = f"instagram/{time.strftime('%Y/%m')}/{path.name}"
    extra = {"ContentType": "video/mp4", "CacheControl": "public, max-age=3600"}
    client.upload_file(str(path), bucket, key, ExtraArgs=extra)
    if public_base:
        return f"{public_base}/{key}"
    if endpoint:
        return f"{endpoint.rstrip('/')}/{bucket}/{key}"
    return f"https://{bucket}.s3.amazonaws.com/{key}"


def upload_local(path: Path, cfg: Cfg | None = None) -> str:
    base = (env("PUBLIC_BASE_URL") or "").rstrip("/")
    if not base:
        raise UploadError(
            "UPLOADER=local است ولی PUBLIC_BASE_URL خالی است. "
            "آدرس عمومی سرور/تانل خود را بدهید، مثلاً https://my-host.example.com"
        )
    subdir = (env("PUBLIC_MEDIA_SUBDIR") or "out").strip("/")
    return f"{base}/{subdir}/{path.name}"


BACKENDS = {
    "uguu": upload_uguu,
    "litterbox": upload_litterbox,
    "catbox": upload_catbox,
    "s3": upload_s3,
    "r2": upload_s3,
    "local": upload_local,
}


def upload(path: str | Path, backend: str | None = None, cfg: Cfg | None = None) -> str:
    """فایل را آپلود می‌کند و URL عمومی برمی‌گرداند."""
    path = Path(path)
    if not path.exists():
        raise UploadError(f"فایل پیدا نشد: {path}")
    backend = (backend or env("UPLOADER", "uguu")).lower()
    func = BACKENDS.get(backend)
    if func is None:
        raise UploadError(f"uploader ناشناخته: {backend} (گزینه‌ها: {', '.join(BACKENDS)})")

    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            url = func(path) if backend != "local" else func(path, cfg)  # type: ignore[call-arg]
            if not url.startswith("http"):
                raise UploadError(f"آدرس برگشتی نامعتبر: {url}")
            return url
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(3 * attempt)
    raise UploadError(f"آپلود با {backend} ناموفق ماند: {last_error}")
