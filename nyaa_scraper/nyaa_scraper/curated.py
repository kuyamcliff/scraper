from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


@dataclass(slots=True)
class CuratedReleaseHint:
    info_hash: Optional[str] = None
    title: Optional[str] = None
    release_group: Optional[str] = None
    score: float = 0.0
    tier: Optional[int] = None
    tags: list[str] = field(default_factory=list)
    source: str = "curated"


class CuratedProvider(Protocol):
    async def lookup(self, *, anilist_id: int, season: int | None = None, episode: int | None = None) -> list[CuratedReleaseHint]: ...


class JsonCuratedProvider:
    """Adapter for a user-supplied curated-release JSON document.

    Shape: {"12345": [{"info_hash":"...", "score": 100, "tier": 1, ...}]}
    This makes curated release knowledge optional and versionable without coupling the engine to an undocumented service.
    """
    def __init__(self, data: dict[str, Any]):
        self.data = data

    async def lookup(self, *, anilist_id: int, season: int | None = None, episode: int | None = None) -> list[CuratedReleaseHint]:
        rows = self.data.get(str(anilist_id), [])
        out = []
        for row in rows:
            out.append(CuratedReleaseHint(info_hash=row.get("info_hash"), title=row.get("title"), release_group=row.get("release_group"), score=float(row.get("score", 0)), tier=row.get("tier"), tags=list(row.get("tags", []))))
        return out
