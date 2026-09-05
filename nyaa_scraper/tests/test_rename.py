import pytest
from nyaa_scraper.models import ParsedTorrent, Release, MatchResult, ScoreBreakdown
from nyaa_scraper.renamer import media_server_name


def test_rename_is_safe():
    t = ParsedTorrent("[G] A/B:C? - S01E01 [1080p].mkv", episode=1, season=1, resolution="1080p", release_group="G")
    name = media_server_name(t, "A/B:C?", anilist_id=123)
    assert "/" not in name and ":" not in name and "?" not in name
    assert "anilist-123" not in name
    assert "S01E01" in name
