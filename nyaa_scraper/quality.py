from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import ParsedTorrent, Release


DEFAULT_POLICY = {
    "min_resolution": "1080p",
    "max_resolution": None,
    "require_known_resolution": True,
    "allowed_sources": [],
    "preferred_sources": ["Remux", "BluRay", "WEB-DL", "WEBRip", "HDTV"],
    "preferred_codecs": ["H.264", "H.265", "AV1"],
    "blocked_codecs": ["AV1"],
    "block_x265_hd": False,
    "require_original_audio": False,
    "preferred_audio_languages": ["Japanese"],
    "required_audio_languages": [],
    "preferred_subtitle_languages": ["English"],
    "required_subtitle_languages": [],
    "prefer_dual_audio": False,
    "prefer_uncensored": False,
    "prefer_10bit": True,
    "allow_hdr": True,
    "require_hdr_for_4k": False,
    "allow_dolby_vision": True,
    "min_seeders": 0,
    "max_size_bytes": None,
    "preferred_size_bytes": None,
    "reject_unknown_codec": False,
    "reject_unknown_source": False,
    "reject_extras": True,
    "reject_bad_terms": True,
    "reject_no_group": False,
    "bad_groups": [],
    "preferred_groups": {},
    "group_aliases": {},
    "bad_title_terms": ["cam", "ts", "tc", "screener", "sample", "trailer", "preview", "ncop", "nced"],
    "service_scores": {},
    "profile_name": "streaming",
}

RESOLUTION_HEIGHTS = {"240p": 240, "360p": 360, "480p": 480, "576p": 576, "720p": 720, "1080p": 1080, "1440p": 1440, "2160p": 2160, "4320p": 4320}


def _norm(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def resolution_height(t: ParsedTorrent) -> int | None:
    if t.height:
        return t.height
    if t.resolution:
        raw = t.resolution.lower().replace("4k", "2160p").replace("uhd", "2160p").replace("fhd", "1080p").replace("hd", "720p")
        return RESOLUTION_HEIGHTS.get(raw)
    return None


def source_key(t: ParsedTorrent) -> str:
    return _norm(t.source)


def load_policy(profile: str = "streaming", path: str | Path | None = None) -> dict[str, Any]:
    data = json.loads(json.dumps(DEFAULT_POLICY))
    if profile == "archival":
        data.update({
            "profile_name": "archival", "min_resolution": "1080p", "preferred_sources": ["Remux", "BluRay", "BDMV"],
            "preferred_codecs": ["H.264", "H.265"], "blocked_codecs": ["AV1"], "prefer_10bit": True,
            "reject_no_group": True, "require_known_resolution": True,
        })
    elif profile == "mobile":
        data.update({
            "profile_name": "mobile", "min_resolution": "720p", "max_resolution": "1080p",
            "preferred_sources": ["WEB-DL", "WEBRip", "BluRay"], "preferred_codecs": ["H.264", "H.265"],
            "blocked_codecs": [], "prefer_10bit": False,
        })
    elif profile == "maximum":
        data.update({
            "profile_name": "maximum", "min_resolution": "1080p", "preferred_sources": ["Remux", "BluRay", "BDMV", "WEB-DL"],
            "blocked_codecs": ["AV1"], "prefer_10bit": True, "require_known_resolution": True,
        })
    if path:
        custom = json.loads(Path(path).read_text(encoding="utf-8"))
        data = _deep_merge(data, custom)
    return data


def _deep_merge(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def rejection_reasons(release: Release, policy: dict[str, Any], expected: dict[str, Any] | None = None) -> list[tuple[str, str]]:
    t = release.parsed
    rejects: list[tuple[str, str]] = []
    min_h = RESOLUTION_HEIGHTS.get(str(policy.get("min_resolution", "0")).lower(), 0)
    max_h = RESOLUTION_HEIGHTS.get(str(policy.get("max_resolution", "0")).lower(), 0) or None
    h = resolution_height(t)

    if policy.get("require_trusted") and not release.trusted:
        rejects.append(("not_trusted", "release is not marked trusted"))
    if release.seeders < int(policy.get("min_seeders", 0)):
        rejects.append(("min_seeders", f"only {release.seeders} seeders; minimum is {policy['min_seeders']}"))
    if policy.get("require_known_resolution") and h is None:
        rejects.append(("unknown_resolution", "resolution is unknown"))
    if h is not None and h < min_h:
        rejects.append(("min_resolution", f"{h}p-class media is below minimum {min_h}p"))
    if max_h is not None and h is not None and h > max_h:
        rejects.append(("max_resolution", f"{h}p-class media exceeds maximum {max_h}p"))
    if policy.get("allowed_sources") and t.source and t.source not in policy["allowed_sources"]:
        rejects.append(("source", f"source {t.source} is not allowed"))
    if policy.get("allowed_sources") and not t.source and policy.get("reject_unknown_source"):
        rejects.append(("unknown_source", "source is unknown"))
    if t.video_codec and any(_norm(t.video_codec) == _norm(x) for x in policy.get("blocked_codecs", [])):
        rejects.append(("blocked_codec", f"codec {t.video_codec} is blocked"))
    if policy.get("reject_unknown_codec") and not t.video_codec:
        rejects.append(("unknown_codec", "video codec is unknown"))
    if policy.get("block_x265_hd") and h and h < 2160 and _norm(t.video_codec) in {"h265", "hevc"}:
        rejects.append(("x265_hd", "x265/HEVC HD is blocked by profile"))
    if policy.get("require_hdr_for_4k") and h and h >= 2160 and not t.hdr and not t.dolby_vision:
        rejects.append(("4k_sdr", "4K release is SDR while HDR is required"))
    if policy.get("required_audio_languages"):
        actual = {_norm(x) for x in (t.audio_languages or [])}
        for lang in policy["required_audio_languages"]:
            if _norm(lang) not in actual:
                rejects.append(("required_audio_language", f"missing required audio language: {lang}"))
    if policy.get("required_subtitle_languages"):
        actual = {_norm(x) for x in (t.subtitle_languages or [])}
        for lang in policy["required_subtitle_languages"]:
            if _norm(lang) not in actual:
                rejects.append(("required_subtitle_language", f"missing required subtitle language: {lang}"))
    if policy.get("reject_extras") and t.is_extra:
        rejects.append(("extra", "release appears to be an extra/preview/trailer/sample"))
    if policy.get("reject_bad_terms"):
        bad_terms = {_norm(x) for x in policy.get("bad_title_terms", [])}
        filename_norm = _norm(t.filename)
        matched = next((term for term in bad_terms if term and term in filename_norm), None)
        if matched:
            rejects.append(("bad_term", f"blocked title term detected: {matched}"))
    if policy.get("reject_no_group") and not t.release_group:
        rejects.append(("no_release_group", "release group is missing"))
    bad_groups = {_norm(x) for x in policy.get("bad_groups", [])}
    if t.release_group and _norm(t.release_group) in bad_groups:
        rejects.append(("bad_group", f"release group {t.release_group} is blocked"))
    if policy.get("max_size_bytes") and release.size_bytes and release.size_bytes > int(policy["max_size_bytes"]):
        rejects.append(("max_size", f"file size {release.size_bytes} exceeds maximum"))

    expected = expected or {}
    if expected.get("season") is not None and t.season is not None and t.season != expected["season"]:
        rejects.append(("season_mismatch", f"season {t.season} does not match requested season {expected['season']}"))
    if expected.get("season") is not None and t.season is None and not t.is_batch and not expected.get("allow_unknown_season", False):
        rejects.append(("unknown_season", "season is unknown for a season-specific request"))
    if expected.get("episode") is not None and t.episode is not None:
        ep = float(expected["episode"])
        end = t.episode_end or t.episode
        if not (t.episode <= ep <= end):
            rejects.append(("episode_mismatch", f"release episodes {t.episode:g}-{end:g} do not cover requested episode {ep:g}"))
    if expected.get("absolute") is not None and t.absolute is not None:
        ep = int(expected["absolute"])
        end = t.absolute_end or t.absolute
        if not (t.absolute <= ep <= end):
            rejects.append(("absolute_mismatch", f"absolute range {t.absolute}-{end} does not cover {ep}"))
    if expected.get("absolute") is not None and t.absolute is None and not expected.get("allow_unknown_absolute", True):
        rejects.append(("unknown_absolute", "absolute episode is unknown for an absolute-number request"))
    return rejects


def score_quality(release: Release, policy: dict[str, Any]) -> tuple[float, dict[str, float]]:
    t = release.parsed
    scores: dict[str, float] = {}
    h = resolution_height(t) or 0
    min_h = RESOLUTION_HEIGHTS.get(str(policy.get("min_resolution", "0")).lower(), 0)
    max_h = RESOLUTION_HEIGHTS.get(str(policy.get("max_resolution", "0")).lower(), 0)

    scores["resolution"] = min(30.0, max(0.0, (h / 1080.0) * 20.0)) if h else 0.0
    if min_h and h >= min_h:
        scores["resolution"] += 4.0
    if max_h and h <= max_h:
        scores["resolution"] += 2.0

    pref_sources = [str(x) for x in policy.get("preferred_sources", [])]
    scores["source"] = max((len(pref_sources) - i) * 5.0 for i, x in enumerate(pref_sources) if t.source and _norm(t.source) == _norm(x)) or 0.0
    if t.source == "Remux": scores["source"] += 10
    elif t.source in {"BluRay", "BDMV"}: scores["source"] += 7
    elif t.source == "WEB-DL": scores["source"] += 4

    codec = _norm(t.video_codec)
    if codec in {_norm(x) for x in policy.get("preferred_codecs", [])}:
        scores["codec"] = 6.0
    if t.bit_depth == 10 and policy.get("prefer_10bit"):
        scores["codec"] = scores.get("codec", 0) + 3.0
    if t.hdr and policy.get("allow_hdr"):
        scores["codec"] = scores.get("codec", 0) + 3.0
    if t.dolby_vision and policy.get("allow_dolby_vision"):
        scores["codec"] = scores.get("codec", 0) + 2.0

    wanted_audio = {_norm(x) for x in policy.get("preferred_audio_languages", [])}
    actual_audio = {_norm(x) for x in t.audio_languages}
    scores["audio"] = float(len(wanted_audio & actual_audio) * 4)
    if policy.get("prefer_dual_audio") and t.dual_audio:
        scores["audio"] += 5
    if t.audio_codec in {"FLAC", "DTS-HD", "TrueHD", "DTS"}:
        scores["audio"] += 2
    wanted_sub = {_norm(x) for x in policy.get("preferred_subtitle_languages", [])}
    actual_sub = {_norm(x) for x in t.subtitle_languages}
    scores["subtitles"] = float(len(wanted_sub & actual_sub) * 4)
    if t.multi_subs:
        scores["subtitles"] += 1

    if policy.get("prefer_uncensored") and t.uncensored:
        scores["preferences"] = 4

    group_score = 0.0
    group_norm = _norm(t.release_group)
    for group, value in (policy.get("preferred_groups") or {}).items():
        if group_norm == _norm(group):
            group_score = float(value)
            break
    scores["release_group"] = min(15.0, group_score)

    seed = max(0, release.seeders)
    scores["availability"] = min(6.0, math.log1p(seed) * 1.2)
    scores["version"] = (3.0 if t.proper or t.repack else 0.0) + (min(2, t.version or 0) * 0.25)
    pref_size = policy.get("preferred_size_bytes")
    if pref_size and release.size_bytes:
        ratio = release.size_bytes / max(1, int(pref_size))
        scores["size"] = max(0.0, 4.0 - abs(math.log(max(ratio, 1e-9))) * 2.0)
    else:
        scores["size"] = 0.0
    if release.trusted:
        scores["preferences"] = scores.get("preferences", 0) + 1.5

    # Negative scoring is intentionally small because hard gates handle unacceptable media.
    penalties = 0.0
    if not t.release_group:
        penalties += 3
    if not t.source:
        penalties += 2
    if not t.video_codec:
        penalties += 1
    scores["penalties"] = -penalties
    total = sum(scores.values())
    return total, scores
