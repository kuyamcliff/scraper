"""Ultimate anime release discovery, parsing, matching and quality-ranking toolkit."""
from .scraper import NyaaScraper, ScrapeConfig, ScrapeResult
from .models import MediaIdentity, EpisodeIdentity, MediaTrack, ParsedTorrent, Release, MatchResult
from .parser import parse
from .matcher import rank_torrents, title_similarity
from .quality import load_policy
from .renamer import media_server_name, batch_rename_plan
from .anilist import AnilistClient
from .curated import CuratedReleaseHint, CuratedProvider, JsonCuratedProvider
from .nyaa import NyaaClient, NyaaEntry

__all__ = ["NyaaScraper", "ScrapeConfig", "ScrapeResult", "MediaIdentity", "EpisodeIdentity", "MediaTrack", "ParsedTorrent", "Release", "MatchResult", "parse", "rank_torrents", "title_similarity", "load_policy", "media_server_name", "batch_rename_plan", "AnilistClient", "CuratedReleaseHint", "CuratedProvider", "JsonCuratedProvider", "NyaaClient", "NyaaEntry"]
__version__ = "2.0.0"
