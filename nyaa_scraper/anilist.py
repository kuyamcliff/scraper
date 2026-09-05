from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import httpx

ANILIST_URL = "https://graphql.anilist.co"

MEDIA_FIELDS = """
fragment MediaFields on Media {
  id idMal title { romaji english native } synonyms format status season seasonYear episodes duration
  startDate { year month day } endDate { year month day } source isAdult genres
  studios(isMain: true) { nodes { name } }
  relations { edges { relationType(version: 2) node { id idMal title { romaji english native } synonyms format status season seasonYear episodes startDate { year month day } } } }
}
"""

SEARCH_QUERY = MEDIA_FIELDS + """query Search($search:String,$page:Int,$perPage:Int,$format_in:[MediaFormat],$status_not:MediaStatus){
Page(page:$page,perPage:$perPage){media(search:$search,type:ANIME,format_in:$format_in,status_not:$status_not,sort:[SEARCH_MATCH,POPULARITY_DESC]){...MediaFields}}
}"""
ID_QUERY = MEDIA_FIELDS + """query Get($id:Int){Media(id:$id,type:ANIME){...MediaFields}}"""
SEASON_QUERY = MEDIA_FIELDS + """query Season($season:MediaSeason,$year:Int,$page:Int,$perPage:Int){Page(page:$page,perPage:$perPage){media(season:$season,seasonYear:$year,type:ANIME,sort:POPULARITY_DESC){...MediaFields}}}"""


class AnilistClient:
    def __init__(self, *, timeout: float = 25.0, cache_ttl: int = 3600, max_concurrency: int = 2):
        self.client = httpx.AsyncClient(timeout=timeout, headers={"Accept": "application/json", "Content-Type": "application/json", "User-Agent": "nyaa-scraper/2.0"})
        self.cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, Any]] = {}
        self._sem = asyncio.Semaphore(max_concurrency)
        self._reset_at = 0.0
        self._remaining = 90

    async def close(self) -> None:
        await self.client.aclose()

    def _cache_get(self, key: str) -> Any:
        value = self._cache.get(key)
        if not value or value[0] < time.time():
            self._cache.pop(key, None)
            return None
        return value[1]

    def _cache_set(self, key: str, value: Any) -> None:
        self._cache[key] = (time.time() + self.cache_ttl, value)

    async def _wait_limit(self) -> None:
        if self._remaining < 3 and self._reset_at > time.time():
            await asyncio.sleep(max(0.0, self._reset_at - time.time()) + 0.25)

    async def _gql(self, query: str, variables: dict[str, Any], attempts: int = 4) -> dict[str, Any]:
        last: Exception | None = None
        for attempt in range(attempts):
            await self._wait_limit()
            try:
                async with self._sem:
                    resp = await self.client.post(ANILIST_URL, json={"query": query, "variables": variables})
                self._remaining = int(resp.headers.get("X-RateLimit-Remaining", self._remaining))
                self._reset_at = float(resp.headers.get("X-RateLimit-Reset", 0) or 0)
                if resp.status_code == 429:
                    wait = float(resp.headers.get("Retry-After", 2 ** attempt))
                    await asyncio.sleep(min(60.0, wait) + 0.2)
                    continue
                if resp.status_code >= 500 and attempt < attempts - 1:
                    await asyncio.sleep(min(10, 2 ** attempt))
                    continue
                resp.raise_for_status()
                payload = resp.json()
                if payload.get("errors"):
                    raise RuntimeError(str(payload["errors"]))
                return payload.get("data", {})
            except (httpx.HTTPError, RuntimeError) as exc:
                last = exc
                if attempt < attempts - 1:
                    await asyncio.sleep(min(10, 2 ** attempt))
        raise RuntimeError(f"AniList request failed: {last}")

    async def search(self, title: str, *, page: int = 1, per_page: int = 25, formats: Optional[list[str]] = None) -> list[dict]:
        key = f"search:{title.casefold()}:{page}:{per_page}:{formats}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        data = await self._gql(SEARCH_QUERY, {"search": title, "page": page, "perPage": per_page, "format_in": formats, "status_not": "NOT_YET_RELEASED"})
        result = data.get("Page", {}).get("media", [])
        self._cache_set(key, result)
        return result

    async def search_all(self, title: str, *, pages: int = 2, per_page: int = 25) -> list[dict]:
        result: list[dict] = []
        for page in range(1, max(1, pages) + 1):
            chunk = await self.search(title, page=page, per_page=per_page)
            result.extend(chunk)
            if len(chunk) < per_page:
                break
        seen: set[int] = set()
        return [x for x in result if x.get("id") not in seen and not seen.add(x.get("id"))]

    async def get_by_id(self, anilist_id: int) -> Optional[dict]:
        key = f"id:{anilist_id}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        data = await self._gql(ID_QUERY, {"id": int(anilist_id)})
        media = data.get("Media")
        self._cache_set(key, media)
        return media

    async def get_season(self, season: str, year: int) -> list[dict]:
        key = f"season:{season}:{year}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        result: list[dict] = []
        page = 1
        while True:
            data = await self._gql(SEASON_QUERY, {"season": season, "year": year, "page": page, "perPage": 50})
            page_data = data.get("Page", {})
            result.extend(page_data.get("media", []))
            if not page_data.get("pageInfo", {}).get("hasNextPage"):
                break
            page += 1
        self._cache_set(key, result)
        return result

    @staticmethod
    def title_variants(media: dict) -> list[str]:
        raw: list[str] = []
        title = media.get("title") or {}
        raw.extend([title.get("english"), title.get("romaji"), title.get("native")])
        raw.extend(media.get("synonyms") or [])
        out: list[str] = []
        seen: set[str] = set()
        for v in raw:
            if not v or not isinstance(v, str): continue
            v = v.strip()
            for candidate in (v, AnilistClient._strip_suffix(v)):
                k = candidate.casefold()
                if candidate and k not in seen:
                    seen.add(k); out.append(candidate)
        return out

    @staticmethod
    def _strip_suffix(title: str) -> str:
        import re
        return re.sub(r"\s*[:\-]\s*(?:season\s*\d+|part\s*\d+|cour\s*\d+|\d+(?:st|nd|rd|th)\s*season)\s*$", "", title, flags=re.I).strip()

# Attach graph traversal without making it part of the network request path for users who don't need it.
async def _franchise_graph(self: "AnilistClient", root_id: int, depth: int = 3) -> dict[int, dict]:
    visited: dict[int, dict] = {}
    frontier = [int(root_id)]
    for _ in range(max(0, depth) + 1):
        next_frontier: list[int] = []
        for mid in frontier:
            if mid in visited:
                continue
            node = await self.get_by_id(mid)
            if not node:
                continue
            visited[mid] = node
            for edge in (node.get("relations") or {}).get("edges", []):
                rel = edge.get("relationType")
                if rel not in {"SEQUEL", "PREQUEL", "PARENT", "SIDE_STORY", "ALTERNATIVE", "SPIN_OFF", "CONTAINS", "COMPILATION"}:
                    continue
                related = edge.get("node") or {}
                rid = related.get("id")
                if rid and rid not in visited:
                    next_frontier.append(int(rid))
        frontier = list(dict.fromkeys(next_frontier))
        if not frontier:
            break
    return visited

AnilistClient.franchise_graph = _franchise_graph
