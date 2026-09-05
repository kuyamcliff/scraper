from nyaa_scraper.models import ParsedTorrent
from nyaa_scraper.matcher import title_similarity, rank_torrents
from nyaa_scraper.quality import load_policy


def test_title_similarity_preserves_stopwords():
    assert title_similarity("Is It Wrong to Try to Pick Up Girls in a Dungeon", ["Is It Wrong to Try to Pick Up Girls in a Dungeon? Altogether"] ) > 65


def test_exact_episode_out_ranks_wrong_episode():
    media = {"id": 1, "format": "TV", "title": {"romaji": "Frieren", "english": "Frieren"}, "episodes": 28}
    variants = ["Frieren"]
    t1 = ParsedTorrent("[G] Frieren - S01E01 [1080p][WEB-DL][H.264]", title="Frieren", season=1, episode=1, resolution="1080p", height=1080, source="WEB-DL", video_codec="H.264", release_group="G")
    t2 = ParsedTorrent("[G] Frieren - S01E02 [2160p][BluRay][H.265]", title="Frieren", season=1, episode=2, resolution="2160p", height=2160, source="BluRay", video_codec="H.265", release_group="G")
    out = rank_torrents([(t1,{"seeders":2}), (t2,{"seeders":200})], media, variants, policy=load_policy("maximum"), expected_season=1, expected_episode=1)
    assert out[0].torrent.episode == 1
    assert any(not x.eligible for x in out)
