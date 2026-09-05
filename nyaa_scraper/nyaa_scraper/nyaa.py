from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlencode

try:
    import feedparser
except ImportError:
    feedparser = None
import xml.etree.ElementTree as ET
import httpx
from bs4 import BeautifulSoup

NYAA_BASE = "https://nyaa.si"
DEFAULT_MIRRORS = [NYAA_BASE, "https://nyaa.land", "https://nyaa.iss.one"]

CAT_ANIME_ENG = "1_2"
CAT_ANIME_ALL = "1_0"
CAT_ANIME_RAW = "1_4"
FILTER_NO_REMAKES = "1"
FILTER_TRUSTED = "2"
FILTER_ALL = "0"
SORT_DATE = "id"
SORT_SEEDERS = "seeders"
SORT_SIZE = "size"


@dataclass(slots=True)
class NyaaEntry:
    id: str
    title: str
    link: str
    torrent_url: str
    magnet: Optional[str]
    seeders: int
    leechers: int
    downloads: int
    size_bytes: int
    size_human: str
    category: str
    trusted: bool
    remake: bool
    date: str
    info_hash: Optional[str] = None
    raw_tags: list[str] = field(default_factory=list)


def _parse_int(s: str) -> int:
    try:
        return int(re.sub(r"[^0-9-]", "", s) or 0)
    except ValueError:
        return 0


def _parse_size(s: str) -> int:
    m = re.match(r"\s*([\d.,]+)\s*(B|KiB|MiB|GiB|TiB|KB|MB|GB|TB)\s*$", s, re.I)
    if not m:
        return 0
    val = float(m.group(1).replace(",", ""))
    unit = m.group(2).upper()
    mul = {"B": 1, "KB": 1000, "MB": 1000**2, "GB": 1000**3, "TB": 1000**4,
           "KIB": 1024, "MIB": 1024**2, "GIB": 1024**3, "TIB": 1024**4}
    return int(val * mul[unit])


class NyaaClient:
    def __init__(self, base_url: str = NYAA_BASE, *, mirrors: Optional[list[str]] = None, timeout: float = 25.0,
                 max_concurrency: int = 4):
        self.base_url = base_url.rstrip("/")
        self.mirrors = list(dict.fromkeys((mirrors or DEFAULT_MIRRORS)))
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=min(timeout, 10)), follow_redirects=True,
            headers={"User-Agent": "nyaa-scraper/2.0 (+https://github.com/)", "Accept": "text/html,application/xml"},
        )
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._health: dict[str, dict[str, float | int]] = {m: {"fails": 0, "last_ok": 0.0} for m in self.mirrors}

    async def close(self) -> None:
        await self.client.aclose()

    def _candidate_bases(self) -> list[str]:
        return sorted(self.mirrors, key=lambda x: (self._health[x]["fails"], -float(self._health[x]["last_ok"])))

    @staticmethod
    def _replace_base(url: str, source_base: str, target_base: str) -> str:
        if url.startswith(source_base):
            return target_base + url[len(source_base):]
        return url

    async def _get(self, path_or_url: str) -> httpx.Response:
        last_exc: Exception | None = None
        for base in self._candidate_bases():
            url = path_or_url if path_or_url.startswith("http") else base + "/" + path_or_url.lstrip("/")
            try:
                async with self._semaphore:
                    resp = await self.client.get(url)
                ctype = resp.headers.get("content-type", "").lower()
                text_head = resp.text[:500].lower()
                if resp.status_code == 429:
                    raise httpx.HTTPStatusError("rate limited", request=resp.request, response=resp)
                if resp.status_code >= 400:
                    raise httpx.HTTPStatusError("http failure", request=resp.request, response=resp)
                if "captcha" in text_head or "cf-chl" in text_head or "challenge-platform" in text_head:
                    raise RuntimeError(f"challenge page from {base}")
                if not ("text/html" in ctype or "application/xhtml" in ctype or "xml" in ctype or not ctype):
                    raise RuntimeError(f"unexpected content type: {ctype}")
                self._health[base]["fails"] = max(0, int(self._health[base]["fails"]) - 1)
                self._health[base]["last_ok"] = time.time()
                return resp
            except Exception as exc:
                last_exc = exc
                self._health[base]["fails"] = int(self._health[base]["fails"]) + 1
                continue
        raise RuntimeError(f"all mirrors failed for {path_or_url}: {last_exc}")

    def _build_url(self, query: str, category: str = CAT_ANIME_ENG, filter_: str = FILTER_ALL,
                   sort: str = SORT_SEEDERS, page: int = 1) -> str:
        params = {"f": category, "c": category, "q": query, "f": filter_, "s": sort, "p": page}
        # Nyaa historically accepts c for category and f for filter; omit duplicate/conflicting keys.
        params = {"c": category, "f": filter_, "q": query, "s": sort, "p": page}
        return "/?" + urlencode(params)

    @staticmethod
    def _parse_html(text: str, source_base: str) -> list[NyaaEntry]:
        soup = BeautifulSoup(text, "lxml")
        table = soup.select_one("table.torrent-list")
        if not table:
            # Detect a site/schema failure separately from a legitimate empty result.
            if "torrent-list" not in text and "nyaa" not in text.lower():
                raise ValueError("Nyaa HTML schema not recognized")
            return []
        rows: list[NyaaEntry] = []
        for row in table.select("tbody tr"):
            cols = row.select("td")
            if len(cols) < 8:
                continue
            title_a = row.select_one("td:nth-child(2) a")
            if not title_a:
                continue
            title = title_a.get_text(" ", strip=True)
            link = title_a.get("href", "")
            if link.startswith("/"):
                link = source_base.rstrip("/") + link
            torrent_a = row.select_one("a[href*='.torrent']")
            torrent_url = torrent_a.get("href") if torrent_a else ""
            if torrent_url and torrent_url.startswith("/"):
                torrent_url = source_base.rstrip("/") + torrent_url
            magnet_a = row.select_one("a[href^='magnet:']")
            magnet = magnet_a.get("href") if magnet_a else None
            category = row.select_one("td:nth-child(1) a")
            category_text = category.get("title", "") if category else ""
            trusted = bool(row.select_one("td:nth-child(2) a.icon-ok, .trusted"))
            remake = bool(row.select_one("td:nth-child(2) a.icon-wrench, .remake"))
            rows.append(NyaaEntry(
                id=(re.search(r"/view/(\d+)", link) or re.search(r"/download/(\d+)", torrent_url or "") or [None, None])[1] or link,
                title=title, link=link, torrent_url=torrent_url, magnet=magnet,
                seeders=_parse_int(cols[5].get_text(strip=True)),
                leechers=_parse_int(cols[6].get_text(strip=True)),
                downloads=_parse_int(cols[7].get_text(strip=True)),
                size_bytes=_parse_size(cols[4].get_text(strip=True)),
                size_human=cols[4].get_text(" ", strip=True), category=category_text,
                trusted=trusted, remake=remake,
                date=(cols[3].get_text(" ", strip=True) if len(cols) > 3 else ""),
                raw_tags=[],
            ))
        return rows

    async def search(self, query: str, *, category: str = CAT_ANIME_ENG, filter_: str = FILTER_ALL,
                     sort: str = SORT_SEEDERS, page: int = 1) -> list[NyaaEntry]:
        path = self._build_url(query, category, filter_, sort, page)
        resp = await self._get(path)
        return self._parse_html(resp.text, resp.request.url.scheme + "://" + resp.request.url.host)

    async def multi_search(self, queries: list[str], *, category: str = CAT_ANIME_ENG, filter_: str = FILTER_ALL,
                           sort: str = SORT_SEEDERS, pages: int = 3, max_results: int = 300) -> list[NyaaEntry]:
        unique = list(dict.fromkeys(q.strip() for q in queries if q and q.strip()))
        tasks = [self.search(q, category=category, filter_=filter_, sort=sort, page=p) for q in unique for p in range(1, max(1, pages) + 1)]
        results: list[NyaaEntry] = []
        for batch_start in range(0, len(tasks), 8):
            batch = tasks[batch_start:batch_start + 8]
            for coro in asyncio.as_completed(batch):
                try:
                    results.extend(await coro)
                except Exception:
                    continue
            if len(results) >= max_results * 2:
                break
        dedup: dict[str, NyaaEntry] = {}
        for item in results:
            key = item.id or item.link or item.title
            dedup[key] = item
        merged = list(dedup.values())
        merged.sort(key=lambda x: (x.seeders, x.downloads), reverse=True)
        return merged[:max_results]

    async def rss(self, query: str) -> list[NyaaEntry]:
        path = "/?" + urlencode({"page": "rss", "c": CAT_ANIME_ENG, "q": query})
        resp = await self._get(path)
        entries: list[NyaaEntry] = []
        if feedparser is not None:
            feed = feedparser.parse(resp.text)
            items = feed.entries
            getter = lambda item, key, default="": getattr(item, key, default)
            for item in items:
                links = getattr(item, "links", [])
                magnet = next((x.href for x in links if getattr(x, "href", "").startswith("magnet:")), None)
                torrent_url = next((x.href for x in links if ".torrent" in getattr(x, "href", "")), "")
                title = getter(item, "title")
                link = getter(item, "link")
                guid = getter(item, "id", link)
                entries.append(NyaaEntry(guid, title, link, torrent_url, magnet, 0, 0, 0, 0, "", CAT_ANIME_ENG, False, False, getter(item, "published")))
        else:
            root = ET.fromstring(resp.text)
            for item in root.findall('.//item'):
                title = item.findtext('title', default='')
                link = item.findtext('link', default='')
                guid = item.findtext('guid', default=link)
                pub = item.findtext('pubDate', default='')
                magnet = None; torrent_url = ''
                for child in list(item):
                    val = child.text or ''
                    if val.startswith('magnet:'): magnet = val
                    if '.torrent' in val: torrent_url = val
                entries.append(NyaaEntry(guid, title, link, torrent_url, magnet, 0, 0, 0, 0, '', CAT_ANIME_ENG, False, False, pub))
        return entries
