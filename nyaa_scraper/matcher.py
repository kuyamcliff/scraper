from __future__ import annotations

import re
from typing import Any, Optional
try:
    from thefuzz import fuzz
except ImportError:
    from difflib import SequenceMatcher
    class _Fuzz:
        @staticmethod
        def ratio(a, b): return SequenceMatcher(None, a, b).ratio() * 100
        @staticmethod
        def token_sort_ratio(a, b):
            aa = " ".join(sorted(a.split())); bb = " ".join(sorted(b.split())); return SequenceMatcher(None, aa, bb).ratio() * 100
    fuzz = _Fuzz()

from .models import MatchResult, ParsedTorrent, Release, Rejection, ScoreBreakdown
from .quality import rejection_reasons, score_quality


def normalize_title(s: str) -> str:
    s = s.casefold()
    s = s.replace("&", " and ")
    s = re.sub(r"[\[\](){}._:;,!?'\"`~|/+\\-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _tokens(s: str) -> set[str]:
    return {x for x in normalize_title(s).split() if len(x) > 0}


def title_similarity(torrent_title: str | None, candidates: list[str]) -> float:
    if not torrent_title or not candidates:
        return 0.0
    tn = normalize_title(torrent_title)
    tt = _tokens(torrent_title)
    best = 0.0
    for cand in candidates:
        cn = normalize_title(cand)
        ct = _tokens(cand)
        if not cn:
            continue
        exact = 100.0 if tn == cn else 0.0
        ratio = fuzz.ratio(tn, cn)
        token_sort = fuzz.token_sort_ratio(tn, cn)
        # Bidirectional token coverage resists both short false positives and harmless suffixes.
        coverage_a = 100.0 * len(tt & ct) / max(1, len(tt))
        coverage_b = 100.0 * len(tt & ct) / max(1, len(ct))
        coverage = 2 * coverage_a * coverage_b / max(1.0, coverage_a + coverage_b)
        candidate_score = exact * 0.28 + ratio * 0.32 + token_sort * 0.20 + coverage * 0.20
        if tt.issubset(ct) or ct.issubset(tt):
            candidate_score += 6
        best = max(best, min(100.0, candidate_score))
    return best


def _media_format(media: dict[str, Any]) -> str:
    return str(media.get("format") or "").upper()


def _expected_episode(media: dict[str, Any], explicit_episode: Optional[float]) -> Optional[float]:
    if explicit_episode is not None:
        return explicit_episode
    return None


def _field_confidence(t: ParsedTorrent, key: str, default: float = 0.45) -> float:
    return float(t.parse_confidence.get(key, default))


def evaluate_release(
    release: Release,
    media: dict[str, Any],
    title_variants: list[str],
    *,
    policy: dict[str, Any],
    expected_season: Optional[int] = None,
    expected_episode: Optional[float] = None,
    expected_absolute: Optional[int] = None,
    allow_related: bool = False,
) -> MatchResult:
    t = release.parsed
    title_score = title_similarity(t.title, title_variants)
    expected = {"season": expected_season, "episode": expected_episode, "absolute": expected_absolute}
    rejects = rejection_reasons(release, policy, expected)

    fmt = _media_format(media)
    if fmt == "MOVIE" and not t.is_movie and t.episode is not None and not t.is_batch:
        rejects.append(("format_mismatch", "target is a movie but release looks like a normal episode"))
    if fmt in {"OVA", "ONA", "SPECIAL"} and t.is_movie and not allow_related:
        rejects.append(("format_mismatch", f"target format {fmt} but release looks like a movie"))

    # A hard floor is used only after title context is considered; 009-1, Eighty-Six and numeric titles must survive.
    title_floor = 72.0
    if title_score < title_floor:
        rejects.append(("title_mismatch", f"title confidence {title_score:.1f} is below {title_floor}"))

    quality_total, qs = score_quality(release, policy)
    b = ScoreBreakdown()
    b.match = title_score * 0.50
    b.source = qs.get("source", 0.0)
    b.resolution = qs.get("resolution", 0.0)
    b.codec = qs.get("codec", 0.0)
    b.audio = qs.get("audio", 0.0)
    b.subtitles = qs.get("subtitles", 0.0)
    b.release_group = qs.get("release_group", 0.0)
    b.size = qs.get("size", 0.0)
    b.availability = qs.get("availability", 0.0)
    b.version = qs.get("version", 0.0)
    b.preferences = qs.get("preferences", 0.0)
    b.penalties = qs.get("penalties", 0.0)

    # Metadata alignment rewards exact structural agreement without letting bad metadata be “bought back” by quality.
    m = 0.0
    if expected_season is not None and t.season == expected_season:
        m += 15
    elif expected_season is None and t.season is not None:
        m += 5
    if expected_episode is not None and t.episode is not None:
        end = t.episode_end or t.episode
        if t.episode <= expected_episode <= end:
            m += 20
    if expected_absolute is not None and t.absolute is not None:
        end = t.absolute_end or t.absolute
        if t.absolute <= expected_absolute <= end:
            m += 20
    if fmt == "MOVIE" and t.is_movie:
        m += 15
    if fmt in {"TV", "TV_SHORT", "ONA"} and (t.episode is not None or t.is_batch):
        m += 8
    b.match += min(35.0, m)

    # Parsing confidence prevents uncertain metadata from looking as strong as explicit metadata.
    confidence = title_score / 100.0
    confidence *= 0.55 + 0.45 * min(1.0, sum(t.parse_confidence.values()) / max(1, len(t.parse_confidence)))
    if expected_episode is not None and t.episode is None:
        confidence *= 0.70
    if expected_season is not None and t.season is None:
        confidence *= 0.75

    reasons = [f"title={title_score:.1f}", f"quality={quality_total:.1f}"]
    if t.source: reasons.append(f"source={t.source}")
    if t.resolution: reasons.append(f"resolution={t.resolution}")
    if t.video_codec: reasons.append(f"codec={t.video_codec}")
    if t.release_group: reasons.append(f"group={t.release_group}")
    if release.seeders: reasons.append(f"seeders={release.seeders}")
    for code, msg in rejects:
        reasons.append(f"REJECT:{code}")

    score = b.total
    if rejects:
        score -= 1000
    return MatchResult(
        release=release,
        score=score,
        confidence=confidence,
        title_score=title_score,
        eligible=not rejects,
        breakdown=b,
        rejections=[Rejection(code, msg) for code, msg in rejects],
        reasons=reasons,
    )


def rank_torrents(
    torrents: list[tuple[ParsedTorrent, dict[str, Any]]],
    media: dict[str, Any],
    title_variants: list[str],
    *,
    policy: dict[str, Any] | None = None,
    min_title_score: float = 0.0,
    expected_season: Optional[int] = None,
    expected_episode: Optional[float] = None,
    expected_absolute: Optional[int] = None,
) -> list[MatchResult]:
    from .quality import load_policy
    policy = policy or load_policy("streaming")
    results: list[MatchResult] = []
    for torrent, meta in torrents:
        release = Release(
            parsed=torrent, source=meta.get("source", "nyaa"), torrent_id=meta.get("id"),
            info_hash=meta.get("info_hash"), torrent_url=meta.get("torrent_url"), magnet=meta.get("magnet"),
            seeders=int(meta.get("seeders", 0) or 0), leechers=int(meta.get("leechers", 0) or 0),
            downloads=int(meta.get("downloads", 0) or 0), size_bytes=int(meta.get("size_bytes", 0) or 0),
            published_at=meta.get("published_at"), trusted=bool(meta.get("trusted", False)), remake=bool(meta.get("remake", False)),
            metadata=meta,
        )
        mr = evaluate_release(release, media, title_variants, policy=policy, expected_season=expected_season,
                              expected_episode=expected_episode, expected_absolute=expected_absolute)
        if mr.title_score >= min_title_score:
            results.append(mr)
    results.sort(key=lambda x: (x.eligible, x.score, x.confidence, x.seeders), reverse=True)
    return results
