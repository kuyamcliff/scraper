from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional

from rich.console import Console
from rich.table import Table

from .anilist import AnilistClient
from .matcher import rank_torrents
from .models import MatchResult
from .nyaa import CAT_ANIME_ENG, FILTER_ALL, FILTER_NO_REMAKES, FILTER_TRUSTED, NyaaClient
from .parser import parse
from .quality import load_policy
from .renamer import batch_rename_plan
from .state import StateStore

console = Console()


@dataclass(slots=True)
class ScrapeConfig:
    query: Optional[str] = None
    anilist_id: Optional[int] = None
    expected_season: Optional[int] = None
    expected_episode: Optional[float] = None
    expected_absolute: Optional[int] = None
    min_resolution: str = "1080p"
    max_resolution: Optional[str] = None
    dual_audio: bool = False
    sub_only: bool = False
    trusted_only: bool = False
    include_related: bool = False
    use_absolute_numbering: bool = False
    min_seeders: int = 0
    max_results: int = 20
    max_pages: int = 3
    max_candidates: int = 300
    min_title_score: float = 72.0
    profile: str = "streaming"
    policy_file: Optional[str] = None
    rss_mode: bool = False
    rss_poll_interval: int = 300
    state_db: str = "nyaa_scraper_state.db"
    mirrors: list[str] = field(default_factory=list)

    def policy(self) -> dict[str, Any]:
        p = load_policy(self.profile, self.policy_file)
        p["min_resolution"] = self.min_resolution
        if self.max_resolution:
            p["max_resolution"] = self.max_resolution
        p["min_seeders"] = self.min_seeders
        if self.sub_only:
            p["prefer_dual_audio"] = False
            p["blocked_codecs"] = p.get("blocked_codecs", [])
        if self.dual_audio:
            p["prefer_dual_audio"] = True
        if self.trusted_only:
            p["require_trusted"] = True
        else:
            p["require_trusted"] = False
        return p


@dataclass(slots=True)
class ScrapeResult:
    media: dict[str, Any]
    matches: list[MatchResult]
    rename_plan: list[dict]
    franchise: dict[int, dict] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "anilist_id": self.media.get("id"),
            "title": (self.media.get("title") or {}).get("english") or (self.media.get("title") or {}).get("romaji"),
            "matches": [x.to_dict() for x in self.matches], "rename_plan": self.rename_plan,
            "franchise": self.franchise,
        }


class NyaaScraper:
    def __init__(self, config: ScrapeConfig, *, anilist: Optional[AnilistClient] = None, nyaa: Optional[NyaaClient] = None,
                 state: Optional[StateStore] = None):
        if not config.query and not config.anilist_id:
            raise ValueError("query or anilist_id is required")
        if config.max_results < 1 or config.max_pages < 1 or config.max_candidates < 1:
            raise ValueError("max_results, max_pages, and max_candidates must be positive")
        if config.min_seeders < 0:
            raise ValueError("min_seeders must be non-negative")
        self.config = config
        self.anilist = anilist or AnilistClient()
        self.nyaa = nyaa or NyaaClient(mirrors=config.mirrors or None)
        self.state = state or StateStore(config.state_db)

    async def close(self) -> None:
        await self.anilist.close(); await self.nyaa.close(); self.state.close()

    async def _resolve(self) -> list[dict]:
        if self.config.anilist_id:
            media = await self.anilist.get_by_id(self.config.anilist_id)
            return [media] if media else []
        candidates: list[dict] = []
        for q in [self.config.query or ""]:
            candidates.extend(await self.anilist.search_all(q, pages=2, per_page=25))
        # Deterministic candidate ordering: popularity/search order preserved, duplicates removed.
        seen: set[int] = set(); out = []
        for x in candidates:
            mid = x.get("id")
            if mid in seen: continue
            seen.add(mid); out.append(x)
        return out[:10]

    async def run(self) -> list[ScrapeResult]:
        media_list = await self._resolve()
        results: list[ScrapeResult] = []
        for media in media_list:
            result = await self._scrape_one(media)
            if result.matches:
                results.append(result)
        return results

    async def _scrape_one(self, media: dict[str, Any]) -> ScrapeResult:
        variants = self.anilist.title_variants(media)
        filter_ = FILTER_TRUSTED if self.config.trusted_only else FILTER_NO_REMAKES if False else FILTER_ALL
        entries = await self.nyaa.multi_search(variants[:10], category=CAT_ANIME_ENG, filter_=filter_, pages=self.config.max_pages, max_results=self.config.max_candidates)
        parsed_pairs = []
        for e in entries:
            if e.seeders < self.config.min_seeders:
                continue
            t = parse(e.title)
            if self.config.dual_audio and not t.dual_audio:
                continue
            if self.config.sub_only and t.dual_audio:
                continue
            if self.config.trusted_only and not e.trusted:
                continue
            parsed_pairs.append((t, {"source": "nyaa", "id": e.id, "info_hash": e.info_hash,
                                     "torrent_url": e.torrent_url, "magnet": e.magnet, "seeders": e.seeders,
                                     "leechers": e.leechers, "downloads": e.downloads, "size_bytes": e.size_bytes,
                                     "trusted": e.trusted, "remake": e.remake, "published_at": e.date, "media": media}))
        matches = rank_torrents(parsed_pairs, media, variants, policy=self.config.policy(), min_title_score=self.config.min_title_score,
                                expected_season=self.config.expected_season, expected_episode=self.config.expected_episode,
                                expected_absolute=self.config.expected_absolute)
        eligible = [m for m in matches if m.eligible][:self.config.max_results]
        for m in eligible:
            self.state.mark_seen(m.release.source, m.release.identity_key, processed=True, matched=True)
        plan = batch_rename_plan(eligible, use_absolute=self.config.use_absolute_numbering) if eligible else []
        franchise = {}
        if self.config.include_related and media.get("id"):
            franchise = await self.anilist.franchise_graph(media["id"]) if hasattr(self.anilist, "franchise_graph") else {}
        return ScrapeResult(media=media, matches=eligible, rename_plan=plan, franchise=franchise)

    async def run_rss(self, callback=None) -> None:
        while True:
            media_list = await self._resolve()
            media = media_list[0] if media_list else None
            if media:
                variants = self.anilist.title_variants(media)
                query = variants[0] if variants else (self.config.query or "")
                entries = await self.nyaa.rss(query)
                for entry in entries:
                    key = entry.id or entry.link or entry.title
                    if self.state.seen("nyaa-rss", key):
                        continue
                    self.state.mark_seen("nyaa-rss", key, processed=False)
                    try:
                        t = parse(entry.title)
                        pairs = [(t, {"source": "nyaa-rss", "id": entry.id, "info_hash": entry.info_hash,
                                      "torrent_url": entry.torrent_url, "magnet": entry.magnet, "seeders": entry.seeders,
                                      "trusted": entry.trusted, "remake": entry.remake, "media": media})]
                        ranked = rank_torrents(pairs, media, variants, policy=self.config.policy(), min_title_score=self.config.min_title_score,
                                               expected_season=self.config.expected_season, expected_episode=self.config.expected_episode,
                                               expected_absolute=self.config.expected_absolute)
                        good = next((x for x in ranked if x.eligible), None)
                        self.state.mark_seen("nyaa-rss", key, processed=True, matched=bool(good))
                        if good and callback:
                            await callback(entry, good)
                    except Exception:
                        # Failed processing remains recorded as unprocessed? Reset it so next poll retries it.
                        self.state.conn.execute("UPDATE seen_release SET processed=0 WHERE source=? AND release_key=?", ("nyaa-rss", key)); self.state.conn.commit()
            await asyncio.sleep(max(10, self.config.rss_poll_interval))

    def print_results(self, results: list[ScrapeResult]) -> None:
        for sr in results:
            title = (sr.media.get("title") or {}).get("english") or (sr.media.get("title") or {}).get("romaji") or "Unknown"
            table = Table(title=f"Results for: {title}", show_lines=True)
            for col in ("Score", "Conf", "Group", "Res", "Source", "Seeds", "Filename"):
                table.add_column(col)
            for mr in sr.matches:
                t = mr.torrent
                table.add_row(f"{mr.score:.1f}", f"{mr.confidence*100:.0f}%", t.release_group or "?", t.resolution or "?",
                              t.source or "?", str(mr.seeders), t.filename[:70])
            console.print(table)
