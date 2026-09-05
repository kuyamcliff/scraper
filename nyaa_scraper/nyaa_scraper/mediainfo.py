from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from .models import MediaTrack, ParsedTorrent


class MediaProbeError(RuntimeError):
    pass


def probe(path: str | Path, *, ffprobe_bin: str = "ffprobe", timeout: float = 30.0) -> dict[str, Any]:
    executable = shutil.which(ffprobe_bin)
    if not executable:
        raise MediaProbeError("ffprobe is not installed or not on PATH")
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(p)
    cmd = [executable, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(p)]
    try:
        completed = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout)
        return json.loads(completed.stdout or "{}")
    except subprocess.TimeoutExpired as exc:
        raise MediaProbeError(f"ffprobe timed out after {timeout}s") from exc
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise MediaProbeError(f"ffprobe failed: {exc}") from exc


def enrich(parsed: ParsedTorrent, media_info: dict[str, Any]) -> ParsedTorrent:
    streams = media_info.get("streams") or []
    fmt = media_info.get("format") or {}
    for stream in streams:
        typ = stream.get("codec_type")
        if typ == "video" and not parsed.width and stream.get("width"):
            parsed.width = int(stream["width"]); parsed.height = int(stream.get("height") or 0)
            parsed.resolution = parsed.resolution or f"{parsed.height}p"
            parsed.video_codec = parsed.video_codec or stream.get("codec_name")
            parsed.video_profile = parsed.video_profile or stream.get("profile")
            parsed.bit_depth = parsed.bit_depth or int(stream.get("bits_per_raw_sample") or 0) or None
            tags = {str(k).casefold(): str(v).casefold() for k, v in (stream.get("tags") or {}).items()}
            if any("dolby vision" in x for x in tags.values()):
                parsed.dolby_vision = True; parsed.hdr = parsed.hdr or "Dolby Vision"
            elif stream.get("color_transfer") in {"smpte2084", "arib-std-b67"}:
                parsed.hdr = parsed.hdr or "HDR"
        elif typ == "audio":
            tags = {str(k).casefold(): str(v) for k, v in (stream.get("tags") or {}).items()}
            parsed.audio_tracks.append(MediaTrack(
                codec=stream.get("codec_name"), language=tags.get("language"),
                channels=float(stream.get("channels")) if stream.get("channels") is not None else None,
                bitrate=int(stream.get("bit_rate")) if str(stream.get("bit_rate") or "").isdigit() else None,
                profile=stream.get("profile"), default=None, forced=None,
                lossless=stream.get("codec_name") in {"flac", "truehd", "alac", "pcm_s16le", "pcm_s24le"},
                atmos="atmos" in str(stream.get("profile") or "").casefold(),
            ))
            lang = tags.get("language")
            if lang and lang not in parsed.audio_languages:
                parsed.audio_languages.append(lang)
        elif typ == "subtitle":
            tags = {str(k).casefold(): str(v) for k, v in (stream.get("tags") or {}).items()}
            lang = tags.get("language")
            if lang and lang not in parsed.subtitle_languages:
                parsed.subtitle_languages.append(lang)
            codec = stream.get("codec_name")
            if codec and codec not in parsed.subtitle_formats:
                parsed.subtitle_formats.append(codec)
    if not parsed.bitrate_bps and str(fmt.get("bit_rate") or "").isdigit():
        parsed.bitrate_bps = int(fmt["bit_rate"])
    if len(parsed.audio_tracks) > 1:
        parsed.dual_audio = parsed.dual_audio or len(set(x.language for x in parsed.audio_tracks if x.language)) > 1
    return parsed
