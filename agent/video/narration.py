"""گویندگی فارسی با edge-tts (رایگان، بدون کلید) + آماده‌سازی صدا با ffmpeg."""
from __future__ import annotations

import asyncio
from pathlib import Path

from ..notify import get_logger
from . import ffmpeg as ff

log = get_logger("narration")

DEFAULT_VOICE = "fa-IR-FaridNeural"
FALLBACK_VOICE = "fa-IR-DilaraNeural"


async def _synth(text: str, out_path: Path, voice: str, rate: str, volume: str) -> None:
    import edge_tts  # type: ignore

    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, volume=volume)
    await communicate.save(str(out_path))


def synthesize(text: str, out_path: Path, voice: str = DEFAULT_VOICE,
               rate: str = "+8%", volume: str = "+0%") -> Path:
    """متن فارسی را به فایل mp3 تبدیل می‌کند (با یک بار تلاش مجدد با گویندهٔ جایگزین)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = (text or "").strip()
    if not text:
        raise ValueError("متن گفتار خالی است")

    last_error: Exception | None = None
    for chosen in [voice, FALLBACK_VOICE, DEFAULT_VOICE]:
        try:
            asyncio.run(_synth(text, out_path, chosen, rate, volume))
            if out_path.exists() and out_path.stat().st_size > 1200:
                return out_path
            last_error = RuntimeError("فایل صوتی خالی برگشت")
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            log.warning("گویندگی با %s ناموفق بود: %s", chosen, exc)
    raise RuntimeError(f"ساخت گویندگی ناموفق بود: {last_error}")


def voice_duration(path: str | Path) -> float:
    return ff.media_duration(path)


def pad_to_duration(src: str | Path, dst: Path, total_seconds: float,
                    lead_in: float = 0.35, rate: int = 24000) -> Path:
    """صدای گفتار را با سکوت ابتدا/انتها به طول دقیق صحنه می‌رساند (mono WAV)."""
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    delay_ms = int(max(0.0, lead_in) * 1000)
    ff.run([
        "-i", str(src),
        "-filter_complex",
        f"[0:a]adelay={delay_ms}:all=1,apad=whole_dur={total_seconds:.3f}[a]",
        "-map", "[a]", "-ac", "1", "-ar", str(rate), "-t", f"{total_seconds:.3f}",
        str(dst),
    ])
    return dst


def concat_audio(parts: list[Path], out_path: Path, rate: int = 24000) -> Path:
    """چسباندن قطعه‌های صوتی با demuxer concat (بدون کدگذاری مجدد)."""
    out_path = Path(out_path)
    listing = out_path.with_suffix(".txt")
    listing.write_text(
        "\n".join(f"file '{p.resolve().as_posix()}'" for p in parts), encoding="utf-8"
    )
    ff.run([
        "-f", "concat", "-safe", "0", "-i", str(listing),
        "-ac", "1", "-ar", str(rate), str(out_path),
    ])
    listing.unlink(missing_ok=True)
    return out_path


def mix_bgm(voice_wav: Path, bgm_path: Path, out_path: Path, bgm_volume: float = 0.12) -> Path:
    """موسیقی پس‌زمینه را زیر گفتار میکس می‌کند (حلقه‌ای، بلندی کنترل‌شده)."""
    out_path = Path(out_path)
    ff.run([
        "-i", str(voice_wav), "-stream_loop", "-1", "-i", str(bgm_path),
        "-filter_complex",
        f"[0:a]volume=1.0[v];[1:a]volume={bgm_volume:.3f}[m];"
        "[v][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]",
        "-map", "[a]", "-ac", "1", "-ar", "24000", str(out_path),
    ])
    return out_path


def apply_loudness(wav_path: Path, out_path: Path, target_lufs: float = -14.0) -> Path:
    """نرمال‌سازی بلندی صدا مطابق استاندارد پلتفرم‌ها."""
    out_path = Path(out_path)
    try:
        ff.run(["-i", str(wav_path), "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
                "-ac", "1", "-ar", "24000", str(out_path)])
        return out_path
    except Exception as exc:  # noqa: BLE001
        log.warning("نرمال‌سازی بلندی صدا ناموفق بود (%s) — نسخهٔ اصلی استفاده می‌شود.", exc)
        return wav_path
