from nyaa_scraper.models import ParsedTorrent, Release
from nyaa_scraper.quality import load_policy, rejection_reasons, score_quality


def rel(**kwargs):
    t = ParsedTorrent(filename=kwargs.pop("filename", "[G] Show - 01 [1080p][BluRay][H.264]"), **kwargs)
    return Release(parsed=t, source="nyaa", seeders=kwargs.pop("seeders", 10) if kwargs else 10)


def test_wrong_episode_is_hard_rejected():
    r = Release(parsed=ParsedTorrent(filename="[G] Show S01E02 1080p", season=1, episode=2, height=1080, resolution="1080p", source="WEB-DL", video_codec="H.264"), source="nyaa", seeders=10)
    assert any(code == "episode_mismatch" for code, _ in rejection_reasons(r, load_policy("streaming"), {"season": 1, "episode": 1}))


def test_unknown_resolution_rejected_in_strict_profile():
    r = Release(parsed=ParsedTorrent(filename="[G] Show - 01", episode=1), source="nyaa", seeders=10)
    assert any(code == "unknown_resolution" for code, _ in rejection_reasons(r, load_policy("archival"), {}))


def test_av1_can_be_blocked():
    p = load_policy("archival")
    r = Release(parsed=ParsedTorrent(filename="[G] Show - 01 [2160p][AV1]", height=2160, resolution="2160p", video_codec="AV1"), source="nyaa", seeders=10)
    assert any(code == "blocked_codec" for code, _ in rejection_reasons(r, p, {}))


def test_quality_is_not_just_resolution():
    p = load_policy("maximum")
    blu = Release(parsed=ParsedTorrent(filename="[G] Show [1080p][BluRay][H.264][10bit]", height=1080, resolution="1080p", source="BluRay", video_codec="H.264", bit_depth=10), source="nyaa", seeders=2)
    web = Release(parsed=ParsedTorrent(filename="[G] Show [1080p][WEB-DL][H.264]", height=1080, resolution="1080p", source="WEB-DL", video_codec="H.264"), source="nyaa", seeders=100)
    a, _ = score_quality(blu, p); b, _ = score_quality(web, p)
    assert a > b
