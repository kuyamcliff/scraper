"""
Real-Debrid client — handles magnet → HTTPS link → download
All traffic over port 443, works in restricted containers.
"""

import asyncio
import os
import time
import httpx
from pathlib import Path
from typing import Optional

RD_BASE = "https://api.real-debrid.com/rest/1.0"


class RealDebridError(Exception):
    pass


class RealDebridClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )

    async def close(self):
        await self.client.aclose()

    async def _get(self, path: str, **kw):
        r = await self.client.get(f"{RD_BASE}{path}", **kw)
        r.raise_for_status()
        return r.json()

    async def _post(self, path: str, **kw):
        r = await self.client.post(f"{RD_BASE}{path}", **kw)
        if r.status_code not in (200, 201, 204):
            raise RealDebridError(f"RD error {r.status_code}: {r.text[:200]}")
        return r.json() if r.content else {}

    async def _delete(self, path: str):
        r = await self.client.delete(f"{RD_BASE}{path}")
        r.raise_for_status()

    # ── account ───────────────────────────────────────────────────────────────
    async def user(self) -> dict:
        return await self._get("/user")

    # ── torrents ──────────────────────────────────────────────────────────────
    async def add_magnet(self, magnet: str) -> str:
        """Add magnet, returns torrent id."""
        data = await self._post("/torrents/addMagnet", data={"magnet": magnet})
        return data["id"]

    async def add_torrent(self, content: bytes) -> str:
        """Add .torrent file bytes, returns torrent id."""
        data = await self._post("/torrents/addTorrent",
            content=content,
            headers={**dict(self.client.headers), "Content-Type": "application/octet-stream"})
        return data["id"]

    async def torrent_info(self, torrent_id: str) -> dict:
        return await self._get(f"/torrents/info/{torrent_id}")

    async def select_files(self, torrent_id: str, file_ids: str = "all"):
        """Select files to download. file_ids: 'all' or '1,2,3'"""
        await self._post(f"/torrents/selectFiles/{torrent_id}",
            data={"files": file_ids})

    async def delete_torrent(self, torrent_id: str):
        await self._delete(f"/torrents/delete/{torrent_id}")

    async def list_torrents(self) -> list:
        return await self._get("/torrents")

    # ── unrestrict ────────────────────────────────────────────────────────────
    async def unrestrict_link(self, link: str) -> dict:
        """Convert RD hosted link to direct HTTPS download link."""
        return await self._post("/unrestrict/link", data={"link": link})

    # ── high-level: magnet → direct links ─────────────────────────────────────
    async def resolve_magnet(
        self,
        magnet: str,
        *,
        poll_interval: float = 3.0,
        timeout: float = 120.0,
        on_status: Optional[callable] = None,
    ) -> list[dict]:
        """
        Full pipeline: magnet → wait for RD to download → return list of
        {filename, filesize, download_url} dicts ready for direct HTTPS download.
        """
        tid = await self.add_magnet(magnet)

        # select all files
        info = await self.torrent_info(tid)
        if info.get("status") in ("magnet_conversion", "waiting_files_selection", "queued"):
            await self.select_files(tid, "all")

        # poll until downloaded
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            info = await self.torrent_info(tid)
            status = info.get("status", "")
            if on_status:
                on_status(status, info)
            if status == "downloaded":
                break
            if status in ("error", "dead", "magnet_error"):
                raise RealDebridError(f"RD torrent failed: {status}")
            await asyncio.sleep(poll_interval)
        else:
            raise RealDebridError("Timeout waiting for RD to download torrent")

        # unrestrict each link
        links = info.get("links", [])
        results = []
        for link in links:
            try:
                unrestricted = await self.unrestrict_link(link)
                results.append({
                    "filename": unrestricted.get("filename", ""),
                    "filesize": unrestricted.get("filesize", 0),
                    "download_url": unrestricted["download"],
                    "mimeType": unrestricted.get("mimeType", ""),
                })
            except Exception as e:
                results.append({"filename": link, "filesize": 0, "download_url": link, "error": str(e)})
        return results

    async def resolve_torrent_file(self, content: bytes, **kw) -> list[dict]:
        """Same as resolve_magnet but takes .torrent file bytes."""
        tid = await self.add_torrent(content)
        info = await self.torrent_info(tid)
        if info.get("status") in ("waiting_files_selection", "queued"):
            await self.select_files(tid, "all")
        # reuse magnet resolve logic from here via poll
        # fake magnet to reuse the same poller:
        deadline = time.monotonic() + kw.get("timeout", 120.0)
        on_status = kw.get("on_status")
        poll_interval = kw.get("poll_interval", 3.0)
        while time.monotonic() < deadline:
            info = await self.torrent_info(tid)
            status = info.get("status", "")
            if on_status:
                on_status(status, info)
            if status == "downloaded":
                break
            if status in ("error", "dead", "magnet_error"):
                raise RealDebridError(f"RD torrent failed: {status}")
            await asyncio.sleep(poll_interval)
        else:
            raise RealDebridError("Timeout waiting for RD")
        links = info.get("links", [])
        results = []
        for link in links:
            try:
                u = await self.unrestrict_link(link)
                results.append({
                    "filename": u.get("filename", ""),
                    "filesize": u.get("filesize", 0),
                    "download_url": u["download"],
                    "mimeType": u.get("mimeType", ""),
                })
            except Exception as e:
                results.append({"filename": link, "filesize": 0, "download_url": link, "error": str(e)})
        return results


async def download_file(url: str, dest: Path, *, on_progress: Optional[callable] = None) -> Path:
    """
    Stream a direct HTTPS link to disk. Works on port 443, full speed.
    on_progress(downloaded_bytes, total_bytes) called every 1MB.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=15)) as client:
        async with client.stream("GET", url, follow_redirects=True) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            chunk_size = 1 << 20  # 1 MB
            with open(dest, "wb") as f:
                async for chunk in r.aiter_bytes(chunk_size):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if on_progress:
                        on_progress(downloaded, total)
    return dest
