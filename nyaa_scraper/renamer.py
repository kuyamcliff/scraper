from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .models import MatchResult, ParsedTorrent


def sanitize(s: str, *, replacement: str = "_") -> str:
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]', replacement, s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s or "Unknown"


def media_server_name(
    torrent: ParsedTorrent,
    media_title: str,
    season: Optional[int] = None,
    use_absolute: bool = False,
    include_quality: bool = True,
    include_group: bool = True,
    include_version: bool = True,
    extension: Optional[str] = None,
    anilist_id: Optional[int] = None,
) -> str:
    base = sanitize(media_title)
    ext = extension or Path(torrent.filename).suffix or ".mkv"
    if not ext.startswith("."):
        ext = "." + ext

    if torrent.is_movie:
        name = base
    elif use_absolute and torrent.absolute is not None:
        ep = f"{torrent.absolute:04d}"
        if torrent.absolute_end is not None:
            ep += f"-{torrent.absolute_end:04d}"
        name = f"{base} - {ep}"
    else:
        s = season if season is not None else (torrent.season if torrent.season is not None else 1)
        if torrent.episode is None:
            name = f"{base} - S{s:02d}"
        elif torrent.episode_end is not None:
            name = f"{base} - S{s:02d}E{int(torrent.episode):02d}-E{int(torrent.episode_end):02d}"
        elif isinstance(torrent.episode, int) or (isinstance(torrent.episode, float) and torrent.episode.is_integer()):
            name = f"{base} - S{s:02d}E{int(torrent.episode):02d}"
        else:
            name = f"{base} - S{s:02d}E{str(torrent.episode).replace('.', '_')}"
        if torrent.episode_title:
            name += f" - {sanitize(torrent.episode_title)}"

    tags: list[str] = []
    if include_quality:
        if torrent.resolution: tags.append(torrent.resolution)
        if torrent.source: tags.append(torrent.source)
        if torrent.video_codec: tags.append(torrent.video_codec)
        if torrent.bit_depth: tags.append(f"{torrent.bit_depth}bit")
        if torrent.hdr: tags.append(torrent.hdr.replace(" ", ""))
        if torrent.audio_codec: tags.append(torrent.audio_codec)
        if torrent.dual_audio: tags.append("Dual-Audio")
    if include_version and torrent.version: tags.append(f"v{torrent.version}")
    if include_group and torrent.release_group: tags.append(torrent.release_group)
    if tags:
        name += " [" + " ".join(sanitize(x) for x in tags) + "]"
    # IDs belong in application state, not normal media-server filenames.
    return sanitize(name) + ext.lower()


def batch_rename_plan(matches: list[MatchResult], *, use_absolute: bool = False, max_name_length: int = 240) -> list[dict]:
    plan: list[dict] = []
    seen: dict[str, str] = {}
    for mr in matches:
        if not mr.eligible:
            continue
        media = mr.release.metadata.get("media") or mr.media if hasattr(mr, "media") else mr.release.metadata.get("media")
        media = media or {}
        title = (media.get("title") or {}).get("english") or (media.get("title") or {}).get("romaji") or mr.torrent.title or "Unknown"
        renamed = media_server_name(mr.torrent, title, season=mr.torrent.season, use_absolute=use_absolute, anilist_id=media.get("id"))
        stem, suffix = renamed.rsplit(".", 1) if "." in renamed else (renamed, "mkv")
        renamed = (stem[: max_name_length - len(suffix) - 1] + "." + suffix) if len(renamed) > max_name_length else renamed
        key = renamed.casefold()
        if key in seen and seen[key] != mr.torrent.filename:
            raise ValueError(f"rename collision: {mr.torrent.filename!r} and {seen[key]!r} both map to {renamed!r}")
        seen[key] = mr.torrent.filename
        plan.append({
            "original": mr.torrent.filename,
            "renamed": renamed,
            "torrent_url": mr.torrent_url,
            "magnet": mr.magnet,
            "score": mr.score,
            "confidence": mr.confidence,
            "group": mr.torrent.release_group,
            "info_hash": mr.release.info_hash,
        })
    return plan
