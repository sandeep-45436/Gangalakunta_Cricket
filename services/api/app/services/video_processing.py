"""
Phase 4 — Video processing engine using FFmpeg.
Handles media duration probing, safe window clamping, clip trimming,
thumbnail generation, and synthetic test video synthesis.
"""
import os
import re
import shutil
import subprocess
import tempfile
from typing import Any, Dict, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


def get_ffmpeg_path() -> str:
    """Resolve FFmpeg executable path."""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass

    found = shutil.which("ffmpeg")
    if found:
        return found

    raise RuntimeError("FFmpeg executable could not be resolved on the system.")


def probe_video_duration(video_path: str) -> Optional[float]:
    """
    Probe the duration (in seconds) of a video file using FFmpeg stderr output.
    """
    if not os.path.exists(video_path):
        return None

    exe = get_ffmpeg_path()
    try:
        proc = subprocess.run(
            [exe, "-i", video_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        # Parse 'Duration: 00:00:12.34'
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
        if match:
            hours = float(match.group(1))
            minutes = float(match.group(2))
            seconds = float(match.group(3))
            return hours * 3600.0 + minutes * 60.0 + seconds
    except Exception as exc:
        logger.warning("Failed to probe video duration: %s", exc)

    return None


def calculate_trim_window(
    marker_sec: float,
    media_duration: Optional[float] = None,
    config_before_sec: float = 4.0,
    config_after_sec: float = 5.0,
) -> Dict[str, float]:
    """
    Safely clamp trim window around marker:
      - start_sec >= 0.0
      - end_sec <= media_duration (if media_duration is known)
      - guarantees duration >= 0.5s
    """
    start_sec = max(0.0, marker_sec - config_before_sec)
    tentative_end = marker_sec + config_after_sec

    if media_duration is not None and media_duration > 0:
        clamped_end = min(media_duration, tentative_end)
        # If marker was very early or near duration end, maintain minimum window
        if clamped_end <= start_sec:
            start_sec = max(0.0, clamped_end - 1.0)
        end_sec = clamped_end
    else:
        end_sec = tentative_end

    clip_duration = max(0.5, end_sec - start_sec)

    return {
        "start_sec": round(start_sec, 2),
        "end_sec": round(end_sec, 2),
        "duration_sec": round(clip_duration, 2),
    }


def extract_clip_and_thumbnail(
    input_path: str,
    marker_sec: float,
    config_before_sec: float = 4.0,
    config_after_sec: float = 5.0,
    output_dir: Optional[str] = None,
    base_name: str = "highlight",
) -> Dict[str, Any]:
    """
    Trim video window around marker and generate a preview thumbnail.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input video file not found at: {input_path}")

    exe = get_ffmpeg_path()
    if not output_dir:
        output_dir = tempfile.mkdtemp(prefix="cricket_hl_")
    os.makedirs(output_dir, exist_ok=True)

    media_duration = probe_video_duration(input_path)
    window = calculate_trim_window(
        marker_sec=marker_sec,
        media_duration=media_duration,
        config_before_sec=config_before_sec,
        config_after_sec=config_after_sec,
    )

    output_clip_path = os.path.join(output_dir, f"{base_name}.mp4")
    output_thumb_path = os.path.join(output_dir, f"{base_name}_thumb.jpg")

    # 1. Trim video
    clip_cmd = [
        exe,
        "-y",
        "-ss",
        str(window["start_sec"]),
        "-i",
        input_path,
        "-t",
        str(window["duration_sec"]),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "fast",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        output_clip_path,
    ]
    proc_clip = subprocess.run(clip_cmd, capture_output=True, text=True, check=False)
    if proc_clip.returncode != 0:
        logger.error("FFmpeg clip trimming failed: %s", proc_clip.stderr)
        raise RuntimeError(f"FFmpeg trim failed with exit code {proc_clip.returncode}: {proc_clip.stderr[-300:]}")

    # 2. Extract thumbnail (near marker offset in trimmed clip or middle)
    thumb_offset = min(config_before_sec, window["duration_sec"] / 2.0)
    thumb_cmd = [
        exe,
        "-y",
        "-ss",
        str(max(0.0, round(thumb_offset, 2))),
        "-i",
        output_clip_path,
        "-vframes",
        "1",
        "-q:v",
        "2",
        output_thumb_path,
    ]
    proc_thumb = subprocess.run(thumb_cmd, capture_output=True, text=True, check=False)
    if proc_thumb.returncode != 0:
        logger.warning("FFmpeg thumbnail generation failed: %s", proc_thumb.stderr)
        # Attempt fallback at frame 0
        subprocess.run(
            [exe, "-y", "-i", output_clip_path, "-vframes", "1", output_thumb_path],
            capture_output=True,
            check=False,
        )

    return {
        "clip_path": output_clip_path,
        "thumbnail_path": output_thumb_path if os.path.exists(output_thumb_path) else None,
        "start_offset_sec": window["start_sec"],
        "end_offset_sec": window["end_sec"],
        "duration_sec": window["duration_sec"],
    }


def create_test_video(output_path: str, duration_sec: float = 12.0) -> str:
    """
    Generate a deterministic synthetic test video for unit/integration testing.
    Uses lavfi testsrc & sine.
    """
    exe = get_ffmpeg_path()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    cmd = [
        exe,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=duration={duration_sec}:size=640x360:rate=24",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={duration_sec}",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-c:a",
        "aac",
        output_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to generate test video: {proc.stderr}")
    return output_path
