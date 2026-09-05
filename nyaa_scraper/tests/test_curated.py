import pytest
from nyaa_scraper.curated import JsonCuratedProvider

@pytest.mark.asyncio
async def test_curated_lookup():
    provider = JsonCuratedProvider({"1": [{"info_hash": "abc", "score": 100, "tier": 1}]})
    out = await provider.lookup(anilist_id=1, season=1, episode=1)
    assert out[0].info_hash == "abc" and out[0].tier == 1
