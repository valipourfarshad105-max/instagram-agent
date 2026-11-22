"""پیدا کردن ffmpeg و توابع کمکی اجرای آن.

ترتیب پیدا کردن: متغیر محیطی FFMPEG_BIN → ffmpeg سیستم → نسخهٔ همراه imageio-ffmpeg.
چون imageio-ffmpeg فقط ffmpeg دارد و ffprobe ندارد، طول فایل صوتی از راه
دیکد‌کردن به WAV محاسبه می‌شود (بدون نیاز به ffprobe).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import wave
from pathlib import Path

from ..config import env
from ..notify import get_logger

log = get_logger("ffmpeg")
_CACHED: str | None = None
_CACHED_PROBE: str | None | bool = False


def ffmpeg_bin() -> str:
    global _CACHED
    if _CACHED:
        return _CACHED
    candidate = env("FFMPEG_BIN")
    if candidate and Path(candidate).exists():
        _CACHED = candidate
        return _CACHED
    system = shutil.which("ffmpeg")
    if system:
        _CACHED = system
        return _CACHED
    try:
        import imageio_ffmpeg  # type: ignore

        _CACHED = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "ffmpeg پیدا نشد. یکی از این راه‌ها: نصب ffmpeg سیستمی "
            "(apt install ffmpeg / brew install ffmpeg)، یا pip install imageio-ffmpeg، "
            "یا تنظیم مسیر در FFMPEG_BIN."
        ) from exc
    return _CACHED


def ffprobe_bin() -> str | None:
    """ffprobe اگر وجود داشته باشد (برای محاسبهٔ سریع طول/حجم)."""
    global _CACHED_PROBE
    if _CACHED_PROBE is not False:
        return _CACHED_PROBE  # type: ignore[return-value]
    probe = shutil.which("ffprobe")
    if not probe:
        guess = Path(ffmpeg_bin()).with_name("ffprobe")
        probe = str(guess) if guess.exists() else None
    _CACHED_PROBE = probe
    return probe


def run(args: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    """اجرای ffmpeg با مدیریت خطا و لاگ خوانا."""
    cmd = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", *args]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        tail = (result.stderr or "").strip().splitlines()[-6:]
        raise RuntimeError("ffmpeg ناموفق بود:\n" + "\n".join(tail))
    return result


def wav_duration(path: str | Path) -> float:
    """طول فایل WAV بدون نیاز به ffprobe."""
    with wave.open(str(path), "rb") as fh:
        return fh.getnframes() / float(fh.getframerate())


def media_duration(path: str | Path) -> float:
    """طول هر فایل صوتی/تصویری: با ffprobe اگر بود، وگرنه دیکد به WAV."""
    probe = ffprobe_bin()
    if probe:
        result = subprocess.run(
            [probe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=120,
        )
        try:
            return float(result.stdout.strip())
        except ValueError:
            pass
    if Path(path).suffix.lower() == ".wav":
        return wav_duration(path)
    tmp = Path(path).with_suffix(".probe.wav")
    run(["-i", str(path), "-ac", "1", "-ar", "24000", str(tmp)], timeout=300)
    length = wav_duration(tmp)
    tmp.unlink(missing_ok=True)
    return length


def has_audio(path: str | Path) -> bool:
    try:
        result = subprocess.run(
            [ffmpeg_bin(), "-hide_banner", "-i", str(path)],
            capture_output=True, text=True, timeout=60,
        )
        return "Audio:" in (result.stderr or "")
    except Exception:  # noqa: BLE001
        return False


def encode_progress(path: str | Path) -> float:  # pragma: no cover - کمکی
    return 0.0


def ffmpeg_version() -> str:
    result = subprocess.run([ffmpeg_bin(), "-version"], capture_output=True, text=True, timeout=60)
    first = (result.stdout or "").splitlines()[0] if result.stdout else "?"
    return first


def silence_wav(path: str | Path, seconds: float, rate: int = 24000) -> Path:
    """ساخت فایل سکوت (برای جاهای خالی صدا)."""
    path = Path(path)
    run([
        "-f", "lavfi", "-i", f"anullsrc=channel_layout=mono:sample_rate={rate}",
        "-t", f"{seconds:.3f}", "-ac", "1", "-ar", str(rate), str(path),
    ])
    return path


_FONT_SAFE = re.compile(r"[^\w\s\-.,:;/@#()!؟]")
