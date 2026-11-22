"""مونتاژ ریلز: فریم‌های فارسی + گویندگی + چسباندن صحنه‌ها + میکس صدا."""
from __future__ import annotations

from pathlib import Path

from ..notify import get_logger
from . import ffmpeg as ff
from .narration import concat_audio, mix_bgm, pad_to_duration, synthesize
from .overlay import render_scene_frame

log = get_logger("reels")


def _scene_durations(post, cfg, voice_files: list[Path]) -> list[float]:
    """طول هر صحنه = سکوت ابتدا + طول گفتار + سکوت انتها (با رعایت سقف کل ویدیو)."""
    lead = float(cfg.video.lead_in)
    gap = float(cfg.video.tail_gap)
    max_total = float(cfg.video.max_duration)

    spoken = [ff.media_duration(f) for f in voice_files]
    durations = [lead + s + gap for s in spoken]

    total = sum(durations)
    if total > max_total:  # کوچک‌کردن سکوت‌ها برای ماندن در سقف
        spare = total - max_total
        reduction = min(spare, max(0.0, (gap - 0.15)) * len(durations))
        gap -= reduction / len(durations)
        durations = [lead + s + gap for s in spoken]
        log.warning("طول ویدیو از سقف بیشتر بود؛ سکوت‌ها کوتاه شدند.")
    if sum(durations) > max_total:
        log.warning("ویدیو با وجود کوتاه‌کردن سکوت‌ها از %s ثانیه بلندتر است.", max_total)
    return durations


def _render_scene_video(frame_png: Path, out_mp4: Path, duration: float, cfg) -> Path:
    """تصویر ثابت → کلیپ ویدیویی با زوم آرام (Ken Burns)."""
    width, height = int(cfg.video.width), int(cfg.video.height)
    fps = int(cfg.video.fps)
    frames = max(1, int(duration * fps))

    if cfg.video.ken_burns:
        rate = 0.12 / frames  # حدود ۱۲٪ زوم در طول صحنه
        vf = (
            f"scale={width * 2}:{height * 2}:flags=lanczos,"
            f"zoompan=z=1+{rate:.7f}*on:d=1:"
            f"x=iw/2-(iw/zoom/2):y=ih/2-(ih/zoom/2):s={width}x{height}:fps={fps},"
            "format=yuv420p"
        )
    else:
        vf = f"scale={width}:{height}:flags=lanczos,format=yuv420p"

    ff.run([
        "-loop", "1", "-framerate", str(fps), "-t", f"{duration:.3f}",
        "-i", str(frame_png),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(fps), "-an",
        str(out_mp4),
    ], timeout=1200)
    return out_mp4


def _concat_videos(parts: list[Path], out_path: Path, cfg) -> Path:
    """چسباندن کلیپ صحنه‌ها. اول بدون کدگذاری؛ در صورت خطا با کدگذاری مجدد."""
    listing = out_path.with_suffix(".txt")
    listing.write_text("\n".join(f"file '{p.resolve().as_posix()}'" for p in parts), encoding="utf-8")
    try:
        ff.run(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out_path)])
    except Exception as exc:  # noqa: BLE001
        log.warning("چسباندن بدون کدگذاری ناموفق بود (%s) — با کدگذاری مجدد تلاش می‌شود.", exc)
        inputs: list[str] = []
        for part in parts:
            inputs += ["-i", str(part)]
        filter_str = "".join(f"[{i}:v]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=0[v]"
        ff.run([*inputs, "-filter_complex", filter_str, "-map", "[v]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-pix_fmt", "yuv420p", str(out_path)], timeout=1800)
    finally:
        listing.unlink(missing_ok=True)
    return out_path


def _mux(video_path: Path, audio_path: Path, out_path: Path, cfg) -> Path:
    """ویدیو و صدا را یکی می‌کند و برای پخش سریع بهینه می‌سازد."""
    ff.run([
        "-i", str(video_path), "-i", str(audio_path),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "1",
        "-shortest", "-movflags", "+faststart", str(out_path),
    ], timeout=1200)
    return out_path


def build_reel(post, cfg, work_dir: Path, keep_temp: bool = False) -> Path:
    """ریلز نهایی را می‌سازد: out/<id>/reel.mp4"""
    work_dir = Path(work_dir)
    (work_dir / "frames").mkdir(parents=True, exist_ok=True)
    (work_dir / "audio").mkdir(parents=True, exist_ok=True)
    (work_dir / "video").mkdir(parents=True, exist_ok=True)

    scenes = post.scenes
    total = len(scenes)
    voice_cfg = cfg.video

    # ۱) گویندگی هر صحنه
    voice_files: list[Path] = []
    for i, scene in enumerate(scenes):
        label = scene.narration or scene.text or f"صحنهٔ {i + 1}"
        mp3 = work_dir / "audio" / f"voice_{i + 1:02d}.mp3"
        log.info("گویندگی صحنهٔ %s/%s ...", i + 1, total)
        synthesize(label, mp3, voice=voice_cfg.voice, rate=voice_cfg.voice_rate,
                   volume=voice_cfg.voice_volume)
        voice_files.append(mp3)

    durations = _scene_durations(post, cfg, voice_files)
    post.meta = {**(post.meta or {}), "scene_durations": [round(d, 2) for d in durations]}
    log.info("طول صحنه‌ها: %s | مجموع %.1f ثانیه",
             " + ".join(f"{d:.1f}" for d in durations), sum(durations))

    # ۲) فریم‌ها + کلیپ هر صحنه
    video_parts: list[Path] = []
    for i, scene in enumerate(scenes):
        frame = work_dir / "frames" / f"frame_{i + 1:02d}.png"
        render_scene_frame(scene, i, total, cfg, frame)
        part = work_dir / "video" / f"scene_{i + 1:02d}.mp4"
        _render_scene_video(frame, part, durations[i], cfg)
        video_parts.append(part)

    # ۳) صدا: هر گفتار با سکوت به طول صحنه می‌رسد، بعد چسبانده می‌شود
    padded: list[Path] = []
    for i, mp3 in enumerate(voice_files):
        wav = work_dir / "audio" / f"scene_{i + 1:02d}.wav"
        pad_to_duration(mp3, wav, durations[i], lead_in=float(cfg.video.lead_in))
        padded.append(wav)
    voice_track = concat_audio(padded, work_dir / "audio" / "voice_track.wav")

    # ۴) موسیقی پس‌زمینه (اختیاری)
    if cfg.video.bgm:
        bgm_path = cfg.get_path("bgm") if hasattr(cfg, "get_path") else Path(cfg.video.bgm)
        if bgm_path.exists():
            voice_track = mix_bgm(voice_track, bgm_path, work_dir / "audio" / "mixed.wav",
                                  bgm_volume=float(cfg.video.bgm_volume))
        else:
            log.warning("فایل موسیقی پیدا نشد: %s", bgm_path)

    # ۵) چسباندن و میکس نهایی
    silent = _concat_videos(video_parts, work_dir / "video" / "video_track.mp4", cfg)
    out_path = work_dir / "reel.mp4"
    _mux(silent, voice_track, out_path, cfg)

    from ..content.images import cover_from_frame

    cover = cover_from_frame(out_path, work_dir / "cover.jpg", at_second=min(1.0, durations[0] * 0.5))
    if cover:
        post.cover_path = str(cover)

    if not keep_temp:
        import shutil

        for folder in ("frames", "video"):
            shutil.rmtree(work_dir / folder, ignore_errors=True)
        # فایل‌های میانی صدا پاک می‌شوند، ولی mp3 گویندگی می‌ماند (برای بازبینی دستی)
        for leftover in (work_dir / "audio").glob("*.wav"):
            leftover.unlink(missing_ok=True)
    return out_path
