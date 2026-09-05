from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass(slots=True)
class MediaIdentity:
    anilist_id: Optional[int] = None
    mal_id: Optional[int] = None
    title_romaji: Optional[str] = None
    title_english: Optional[str] = None
    title_native: Optional[str] = None
    synonyms: list[str] = field(default_factory=list)
    format: Optional[str] = None
    status: Optional[str] = None
    season_name: Optional[str] = None
    season_year: Optional[int] = None
    episodes: Optional[int] = None
    duration: Optional[int] = None
    is_adult: bool = False
    source: Optional[str] = None
    genres: list[str] = field(default_factory=list)
    studios: list[str] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)

    @property
    def preferred_title(self) -> str:
        return self.title_english or self.title_romaji or self.title_native or "Unknown"

    @property
    def aliases(self) -> list[str]:
        values = [self.title_english, self.title_romaji, self.title_native, *self.synonyms]
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value and value.strip() and value.casefold() not in seen:
                seen.add(value.casefold())
                result.append(value.strip())
        return result

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EpisodeIdentity:
    season: Optional[int] = None
    episode: Optional[float] = None
    episode_end: Optional[float] = None
    absolute: Optional[int] = None
    absolute_end: Optional[int] = None
    special: Optional[int] = None
    episode_title: Optional[str] = None
    air_date: Optional[str] = None

    @property
    def is_range(self) -> bool:
        return self.episode_end is not None or self.absolute_end is not None


@dataclass(slots=True)
class MediaTrack:
    codec: Optional[str] = None
    language: Optional[str] = None
    channels: Optional[float] = None
    bitrate: Optional[int] = None
    profile: Optional[str] = None
    default: Optional[bool] = None
    forced: Optional[bool] = None
    lossless: Optional[bool] = None
    atmos: Optional[bool] = None


@dataclass(slots=True)
class ParsedTorrent:
    filename: str
    release_group: Optional[str] = None
    title: Optional[str] = None
    season: Optional[int] = None
    episode: Optional[float] = None
    episode_end: Optional[float] = None
    absolute: Optional[int] = None
    absolute_end: Optional[int] = None
    special: Optional[int] = None
    episode_title: Optional[str] = None
    air_date: Optional[str] = None
    is_batch: bool = False
    is_movie: bool = False
    is_ova: bool = False
    is_ona: bool = False
    is_special: bool = False
    is_extra: bool = False
    resolution: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    source: Optional[str] = None
    web_service: Optional[str] = None
    video_codec: Optional[str] = None
    video_profile: Optional[str] = None
    bit_depth: Optional[int] = None
    hdr: Optional[str] = None
    dolby_vision: bool = False
    frame_rate: Optional[float] = None
    bitrate_bps: Optional[int] = None
    audio_codec: Optional[str] = None
    audio_tracks: list[MediaTrack] = field(default_factory=list)
    audio_languages: list[str] = field(default_factory=list)
    subtitle_languages: list[str] = field(default_factory=list)
    subtitle_formats: list[str] = field(default_factory=list)
    dual_audio: bool = False
    multi_subs: bool = False
    uncensored: bool = False
    version: Optional[int] = None
    proper: bool = False
    repack: bool = False
    retag: bool = False
    crc32: Optional[str] = None
    info_hash: Optional[str] = None
    raw_tags: list[str] = field(default_factory=list)
    parse_confidence: dict[str, float] = field(default_factory=dict)
    parser_warnings: list[str] = field(default_factory=list)

    @property
    def episode_identity(self) -> EpisodeIdentity:
        return EpisodeIdentity(
            season=self.season, episode=self.episode, episode_end=self.episode_end,
            absolute=self.absolute, absolute_end=self.absolute_end, special=self.special,
            episode_title=self.episode_title, air_date=self.air_date,
        )

    def has_known_resolution(self) -> bool:
        return self.width is not None or self.height is not None or self.resolution is not None

    def normalized_group(self) -> str:
        return (self.release_group or "").strip()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Release:
    parsed: ParsedTorrent
    source: str
    torrent_id: Optional[str] = None
    info_hash: Optional[str] = None
    torrent_url: Optional[str] = None
    magnet: Optional[str] = None
    seeders: int = 0
    leechers: int = 0
    downloads: int = 0
    size_bytes: int = 0
    published_at: Optional[str] = None
    trusted: bool = False
    remake: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def identity_key(self) -> str:
        if self.info_hash:
            return f"hash:{self.info_hash.lower()}"
        if self.torrent_id:
            return f"{self.source}:{self.torrent_id}"
        return f"title:{self.parsed.filename.casefold()}"


@dataclass(slots=True)
class Rejection:
    code: str
    message: str
    severity: str = "hard"


@dataclass(slots=True)
class ScoreBreakdown:
    match: float = 0.0
    source: float = 0.0
    resolution: float = 0.0
    codec: float = 0.0
    audio: float = 0.0
    subtitles: float = 0.0
    release_group: float = 0.0
    size: float = 0.0
    availability: float = 0.0
    version: float = 0.0
    curated: float = 0.0
    preferences: float = 0.0
    penalties: float = 0.0
    confidence: float = 0.0

    @property
    def total(self) -> float:
        return sum((self.match, self.source, self.resolution, self.codec, self.audio,
                    self.subtitles, self.release_group, self.size, self.availability,
                    self.version, self.curated, self.preferences, self.penalties))

    def to_dict(self) -> dict[str, float]:
        data = asdict(self)
        data["total"] = self.total
        return data


@dataclass(slots=True)
class MatchResult:
    release: Release
    score: float
    confidence: float
    title_score: float
    eligible: bool
    breakdown: ScoreBreakdown
    rejections: list[Rejection] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @property
    def torrent(self) -> ParsedTorrent:
        return self.release.parsed

    @property
    def torrent_url(self) -> Optional[str]:
        return self.release.torrent_url

    @property
    def magnet(self) -> Optional[str]:
        return self.release.magnet

    @property
    def seeders(self) -> int:
        return self.release.seeders

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.torrent.filename,
            "score": round(self.score, 4),
            "confidence": round(self.confidence, 4),
            "title_score": round(self.title_score, 4),
            "eligible": self.eligible,
            "torrent_url": self.torrent_url,
            "magnet": self.magnet,
            "seeders": self.seeders,
            "info_hash": self.release.info_hash,
            "breakdown": self.breakdown.to_dict(),
            "rejections": [asdict(x) for x in self.rejections],
            "reasons": self.reasons,
            "parsed": self.torrent.to_dict(),
        }
