from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

try:
    import aniparse as _aniparse
except ImportError:  # optional fallback for environments without the dependency
    _aniparse = None

from .models import MediaTrack, ParsedTorrent


RESOLUTION_MAP = {
    "4320p": (7680, 4320), "8k": (7680, 4320),
    "2160p": (3840, 2160), "4k": (3840, 2160), "uhd": (3840, 2160),
    "1440p": (2560, 1440), "2k": (2560, 1440),
    "1080p": (1920, 1080), "fhd": (1920, 1080),
    "720p": (1280, 720), "hd": (1280, 720),
    "576p": (720, 576), "480p": (720, 480), "360p": (640, 360),
    "240p": (426, 240),
}

SOURCE_ALIASES = {
    "bluray": "BluRay", "blu-ray": "BluRay", "bd": "BluRay", "bdrip": "BluRay", "brrip": "BluRay",
    "bdmv": "BDMV", "remux": "Remux", "web-dl": "WEB-DL", "webdl": "WEB-DL",
    "webrip": "WEBRip", "web": "WEB", "hdtv": "HDTV", "dvdrip": "DVDRip", "dvd": "DVD",
    "vhs": "VHS", "tv": "TV",
}

CODEC_ALIASES = {
    "h.264": "H.264", "h264": "H.264", "avc": "H.264", "x264": "H.264",
    "h.265": "H.265", "h265": "H.265", "hevc": "H.265", "x265": "H.265",
    "av1": "AV1", "vp9": "VP9", "mpeg-4": "MPEG-4", "mpeg4": "MPEG-4",
}

AUDIO_CODECS = {
    "flac": "FLAC", "aac": "AAC", "ac3": "AC-3", "eac3": "E-AC-3", "ddp": "E-AC-3",
    "dts": "DTS", "dts-hd": "DTS-HD", "truehd": "TrueHD", "opus": "Opus", "vorbis": "Vorbis",
    "mp3": "MP3", "alac": "ALAC", "pcm": "PCM", "ape": "APE",
}

LANG_ALIASES = {
    "ja": "Japanese", "jpn": "Japanese", "jp": "Japanese", "japanese": "Japanese",
    "en": "English", "eng": "English", "english": "English", "dub": "English",
    "fr": "French", "fra": "French", "fre": "French", "de": "German", "ger": "German", "deu": "German",
    "es": "Spanish", "spa": "Spanish", "pt": "Portuguese", "por": "Portuguese",
    "it": "Italian", "ita": "Italian", "zh": "Chinese", "chi": "Chinese", "zho": "Chinese",
    "ko": "Korean", "kor": "Korean", "ru": "Russian", "rus": "Russian",
}

RE_BAD_EXT = re.compile(r"\.(?:mkv|mp4|avi|ts|m2ts|webm|mov|flv|wmv|zip|7z|rar)$", re.I)
RE_GROUP = re.compile(r"^\s*\[([^\]]+)\]")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_RES = re.compile(r"(?<![A-Za-z])(4320p|2160p|4K|UHD|1440p|2K|1080p|FHD|720p|576p|480p|360p|240p)(?![A-Za-z])", re.I)
RE_RES_DIM = re.compile(r"\b(\d{3,4})x(\d{3,4})\b", re.I)
RE_SOURCE = re.compile(r"\b(Blu-?Ray|BDMV|BDRip|BRRip|Remux|WEB-?DL|WEBRip|WEB|HDTV|DVDRip|DVD|VHS)\b", re.I)
RE_VCODEC = re.compile(r"\b(H\.265|H265|HEVC|x265|H\.264|H264|AVC|x264|AV1|VP9|MPEG-?4)\b", re.I)
RE_ACODEC = re.compile(r"\b(DTS-HD|DTS|TrueHD|E-?AC-?3|DDP|AC-?3|FLAC|AAC|Opus|Vorbis|MP3|ALAC|PCM|APE)\b", re.I)
RE_BITS = re.compile(r"\b(8|10|12)[- ]?bit\b|\bHi10P\b", re.I)
RE_HDR = re.compile(r"\b(Dolby[ .-]?Vision|DV|HDR10\+?|HDR|HLG|SDR)\b", re.I)
RE_FPS = re.compile(r"\b(\d{2,3}(?:\.\d{1,3})?)\s*fps\b", re.I)
RE_VERSION = re.compile(r"\bv(\d+)\b", re.I)
RE_CRC = re.compile(r"\b([0-9A-Fa-f]{8})\b")
RE_SEASON_WORD = re.compile(r"\bSeason\s*(?P<s>\d{1,3})\b", re.I)
RE_ORDINAL_SEASON = re.compile(r"\b(?P<s>\d{1,2})(?:st|nd|rd|th)\s*Season\b", re.I)
RE_EP_SE = re.compile(r"\bS(?P<s>\d{1,3})\s*E(?P<e1>\d{1,4})(?:\s*[-~+&]\s*E?(?P<e2>\d{1,4}))?\b", re.I)
RE_EP_X = re.compile(r"\b(?P<s>\d{1,2})x(?P<e1>\d{1,4})(?:[-~](?P<e2>\d{1,4}))?\b", re.I)
RE_EP_WORD = re.compile(r"\b(?:EP?|Episode)\.?\s*(?P<e1>\d{1,4})(?:\s*[-~+&]\s*(?P<e2>\d{1,4}))?\b", re.I)
RE_ABSOLUTE = re.compile(r"(?:^|[\s\-_])(?P<e1>\d{3,4})(?:\s*[-~+&]\s*(?P<e2>\d{3,4}))?(?=$|[\s\-_\[])" )
RE_EP_RANGE = re.compile(r"\b(?P<e1>\d{1,3})\s*[-~+&]\s*(?P<e2>\d{1,3})\b")
RE_RANGE = re.compile(r"\b(?P<e1>\d{1,3})\s*[-~+&]\s*(?P<e2>\d{1,3})\b")
RE_STANDALONE_EP = re.compile(r"(?:^|[-\s])(?P<e>\d{1,4})(?:v\d+)?(?=\s*(?:\[|\(|$))", re.I)
RE_FLOAT_EP = re.compile(r"\b(?P<e>\d{1,3}\.5)\b")
RE_DATE = re.compile(r"\b(?:19|20)\d{2}[._-]\d{2}[._-]\d{2}\b")

BAD_TERMS = {
    "sample": "sample", "trailer": "trailer", "preview": "preview", "pv": "pv", "cm": "cm",
    "ncop": "ncop", "nced": "nced", "menu": "menu", "extras": "extras", "bonus": "bonus",
    "raw": "raw", "cam": "cam", "ts": "ts", "tc": "tc", "screener": "screener",
}


def _normalize_tag(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("_", " ").strip())


def _parse_number(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    return float(value) if "." in value else float(int(value))


def _canonical_resolution(width: int, height: int) -> str:
    labels = sorted(((abs(height - h), key) for key, (_, h) in RESOLUTION_MAP.items()), key=lambda x: x[0])
    return labels[0][1] if labels else f"{height}p"


def _extract_languages(text: str) -> list[str]:
    out: list[str] = []
    lowered = re.sub(r"[._\-]+", " ", text).lower()
    for token, canonical in LANG_ALIASES.items():
        if re.search(rf"(?<![a-z]){re.escape(token)}(?![a-z])", lowered) and canonical not in out:
            out.append(canonical)
    if re.search(r"dual\s*audio|dual\s*audio", lowered) and "English" not in out:
        out.append("English")
    return out


def _fallback_parse(filename: str) -> ParsedTorrent:
    r = ParsedTorrent(filename=filename)
    name = RE_BAD_EXT.sub("", Path(filename).name)
    work = name.replace("_", " ")

    group = RE_GROUP.match(work)
    if group:
        r.release_group = _normalize_tag(group.group(1))
        work = work[group.end():].lstrip()

    r.raw_tags = [x.strip() for x in re.findall(r"\[([^\]]+)\]|\(([^\)]+)\)", name) for x in x if x.strip()]
    lowered = work.lower()
    r.is_batch = bool(re.search(r"\b(batch|complete|complete series|box set|collection|season pack)\b", lowered))
    r.is_movie = bool(re.search(r"\b(movie|film)\b", lowered))
    r.is_ova = bool(re.search(r"\bova\b", lowered))
    r.is_ona = bool(re.search(r"\bona\b", lowered))
    r.is_special = bool(re.search(r"\b(special|sp\d+)\b", lowered))
    r.is_extra = any(re.search(rf"\b{re.escape(x)}\b", lowered) for x in BAD_TERMS)
    r.dual_audio = bool(re.search(r"\bdual[ ._-]?audio\b|\bmulti[ ._-]?audio\b|\bdual\b", lowered))
    r.multi_subs = bool(re.search(r"\bmulti[ ._-]?subs?\b|\bmultiple[ ._-]?subs?\b", lowered))
    r.uncensored = bool(re.search(r"\buncensored\b|\buncut\b", lowered))
    r.proper = bool(re.search(r"\bproper\b", lowered))
    r.repack = bool(re.search(r"\brepack\b", lowered))
    r.retag = bool(re.search(r"\bretag(?:ged)?\b", lowered))

    for m in RE_RES_DIM.finditer(work):
        w, h = int(m.group(1)), int(m.group(2))
        r.width, r.height, r.resolution = w, h, _canonical_resolution(w, h)
        break
    if not r.resolution:
        m = RE_RES.search(work)
        if m:
            key = m.group(1).lower()
            r.resolution = key
            r.width, r.height = RESOLUTION_MAP.get(key, (None, None))
            if r.resolution == "fhd":
                r.resolution = "1080p"
            elif r.resolution == "hd":
                r.resolution = "720p"
            elif r.resolution == "uhd":
                r.resolution = "2160p"
    m = RE_SOURCE.search(work)
    if m:
        r.source = SOURCE_ALIASES.get(m.group(1).lower(), m.group(1))
    m = RE_VCODEC.search(work)
    if m:
        r.video_codec = CODEC_ALIASES.get(m.group(1).lower(), m.group(1))
    m = RE_ACODEC.search(work)
    if m:
        r.audio_codec = AUDIO_CODECS.get(m.group(1).lower(), m.group(1))
    m = RE_BITS.search(work)
    if m:
        r.bit_depth = 10 if "10" in m.group(0) or "hi10" in m.group(0).lower() else (12 if "12" in m.group(0) else 8)
    m = RE_HDR.search(work)
    if m:
        hdr = m.group(1).lower().replace(" ", "")
        r.dolby_vision = hdr in {"dv", "dolbyvision"}
        r.hdr = "Dolby Vision" if r.dolby_vision else ("HDR10+" if "hdr10+" in hdr else ("HDR10" if "hdr10" in hdr else hdr.upper()))
    m = RE_FPS.search(work)
    if m:
        r.frame_rate = float(m.group(1))
    m = RE_VERSION.search(work)
    if m:
        r.version = int(m.group(1))
    m = RE_CRC.search(work)
    if m and not (1900 <= int(m.group(1), 16) <= 2100):
        r.crc32 = m.group(1).upper()

    sm = RE_EP_SE.search(work)
    if sm:
        r.season = int(sm.group("s"))
        r.episode = _parse_number(sm.group("e1"))
        r.episode_end = _parse_number(sm.groupdict().get("e2"))
    else:
        season_m = RE_SEASON_WORD.search(work) or RE_ORDINAL_SEASON.search(work)
        if season_m:
            r.season = int(season_m.group("s"))
        # Range handling is contextual: "Season 3 - 01" means season 3, episode 1;
        # "01-12" means an episode batch; "009-1" is a numeric title, not a range.
        range_m = RE_EP_RANGE.search(work)
        if range_m:
            a, b = int(range_m.group("e1")), int(range_m.group("e2"))
            raw_range = range_m.group(0)
            if r.season is not None and a == r.season and b <= 99:
                r.episode = float(b)
            elif re.match(r"^0\d{2,}\s*-\s*\d{1,2}$", raw_range.strip()):
                range_m = None
            elif not (1900 <= a <= 2100 or 1900 <= b <= 2100):
                r.episode, r.episode_end, r.is_batch = float(a), float(b), True
        if range_m is None and r.episode is None:
            # 1x08 / 12x03 style season/episode notation.
            xm = RE_EP_X.search(work)
            if xm:
                r.season = r.season if r.season is not None else int(xm.group("s"))
                r.episode = _parse_number(xm.group("e1"))
                r.episode_end = _parse_number(xm.groupdict().get("e2"))
        if range_m is None and r.episode is None:
            fm = RE_FLOAT_EP.search(work)
            if fm:
                r.episode = float(fm.group("e")); r.is_special = True
            else:
                # Prefer a number immediately after a release-title separator. This handles
                # "Title - 01v2 - Episode Name" while not mistaking 009-1 for an episode.
                mid = re.findall(r"(?:^|\s[-–]\s)(\d{1,4})(?:v\d+)?(?=\s[-–]_?\s|\s*\[|\s*\(|$)", work)
                standalone = RE_STANDALONE_EP.findall(work)
                candidates = mid or standalone
                if candidates:
                    val = int(candidates[-1])
                    if not (1900 <= val <= 2100):
                        r.episode = float(val)
                        if val >= 100 and r.season is None:
                            r.absolute = val

    # Absolute numbering is useful even when also carrying a season/episode.
    if r.absolute is None:
        am = RE_ABSOLUTE.search(work)
        if am:
            a, b = int(am.group("e1")), am.group("e2")
            if a >= 100 or b:
                r.absolute = a; r.absolute_end = int(b) if b else None

    date = RE_DATE.search(work)
    if date:
        r.air_date = date.group(0).replace(".", "-").replace("_", "-")

    # Remove metadata blocks before title extraction, preserving parenthesized title text only when it is not metadata-like.
    title = re.sub(r"\[[^\]]*\]|\([^\)]*(?:1080p|720p|x264|x265|hevc|flac|aac|dual|batch|bluray|web[- ]?dl)[^\)]*\)", " ", work, flags=re.I)
    protected: dict[str, str] = {}
    def _protect_numeric_title(m):
        key = f"__NUMTITLE{len(protected)}__"
        protected[key] = m.group(0)
        return key
    title = re.sub(r"\b0\d{2,}\s*-\s*\d{1,2}\b", _protect_numeric_title, title)
    patterns = [RE_EP_SE, RE_EP_X, RE_EP_WORD, RE_ABSOLUTE, RE_FLOAT_EP, RE_RES_DIM, RE_RES,
                RE_SOURCE, RE_VCODEC, RE_ACODEC, RE_BITS, RE_HDR, RE_FPS, RE_VERSION, RE_SEASON_WORD, RE_ORDINAL_SEASON]
    for pattern in patterns:
        title = pattern.sub(" ", title)
    title = RE_EP_RANGE.sub(" ", title)
    title = RE_STANDALONE_EP.sub(" ", title)
    for key, value in protected.items():
        title = title.replace(key, value)
    title = re.sub(r"\b(?:batch|complete|movie|film|ova|ona|special|uncensored|uncut|proper|repack|retag(?:ged)?)\b", " ", title, flags=re.I)
    # Episode titles and version suffixes often follow the episode number; the series title ends at the marker.
    if r.episode is not None:
        ep_int = int(r.episode) if float(r.episode).is_integer() else str(r.episode).replace(".", "_")
        marker = re.search(rf"\s[-–]\s0*{re.escape(str(ep_int))}(?:v\d+)?\b", title, re.I)
        if marker:
            title = title[:marker.start()]
    title = re.sub(r"[_\.]+", " ", title)
    title = re.sub(r"\s+", " ", title).strip(" -_.")
    if title:
        title = re.sub(r"\s*-\s*$", "", title).strip()
    r.title = title or None

    r.audio_languages = _extract_languages(work)
    r.dual_audio = r.dual_audio or len(r.audio_languages) > 1
    r.parse_confidence = {
        "release_group": 0.98 if r.release_group else 0.2,
        "resolution": 0.98 if r.width and r.height else (0.9 if r.resolution else 0.15),
        "season": 0.98 if r.season is not None else 0.2,
        "episode": 0.98 if r.episode is not None else 0.2,
        "title": 0.85 if r.title else 0.1,
    }
    if r.absolute is not None:
        r.parse_confidence["absolute"] = 0.9
    return r


def _apply_aniparse_enrichment(result: ParsedTorrent, filename: str) -> ParsedTorrent:
    if _aniparse is None:
        return result
    try:
        parsed: dict[str, Any] = _aniparse.parse(filename)
    except Exception as exc:
        result.parser_warnings.append(f"aniparse failed: {exc}")
        return result

    def first(*keys: str) -> Any:
        for key in keys:
            value = parsed.get(key)
            if value is not None and value != [] and value != "":
                return value[0] if isinstance(value, list) and value else value
        return None

    if not result.release_group:
        value = first("release_group", "group")
        if isinstance(value, str):
            result.release_group = value
    if not result.title:
        series = parsed.get("series") or []
        if series and isinstance(series[0], dict):
            result.title = series[0].get("title") or first("title")
            eps = series[0].get("episode") or []
            if eps:
                ep = eps[0]
                if isinstance(ep, dict):
                    result.episode = result.episode if result.episode is not None else ep.get("number")
                    result.episode_title = result.episode_title or ep.get("title")
            seas = series[0].get("season") or []
            if seas and isinstance(seas[0], dict):
                result.season = result.season if result.season is not None else seas[0].get("number")
    if not result.resolution:
        dims = parsed.get("video_resolution")
        if dims and isinstance(dims[0], dict):
            result.width = result.width or dims[0].get("video_width")
            result.height = result.height or dims[0].get("video_height")
            if result.height:
                result.resolution = _canonical_resolution(result.width or 0, result.height)
    result.audio_codec = result.audio_codec or first("audio_term")
    result.video_codec = result.video_codec or first("video_term")
    result.source = result.source or first("source")
    result.crc32 = result.crc32 or first("file_checksum")
    result.parser_warnings.append("primary parser: contextual aniparse + deterministic enrichment")
    return result


def parse(filename: str, *, use_aniparse: bool = True) -> ParsedTorrent:
    if not filename or not filename.strip():
        raise ValueError("filename must not be empty")
    result = _fallback_parse(filename)
    if use_aniparse:
        result = _apply_aniparse_enrichment(result, filename)
    return result
