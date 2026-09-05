from nyaa_scraper.state import StateStore

def test_persistent_seen(tmp_path):
    p = tmp_path / "state.db"
    a = StateStore(p); a.mark_seen("rss", "abc"); a.close()
    b = StateStore(p); assert b.seen("rss", "abc"); b.close()
