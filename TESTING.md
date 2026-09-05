# Test matrix

The offline regression corpus intentionally exercises numeric titles, season/episode notation, absolute numbering, ranges, batches, specials, movies, OVA/ONA, dimensions, codecs, HDR/DV, audio, subtitles, versions, repacks, and common naming variants across major anime franchises.

The suite is designed to run without internet access. Network providers are not mocked in these tests because provider behavior is explicitly isolated in the client adapters.

Run:

```bash
PYTHONPATH=. pytest -q
python -m py_compile nyaa_scraper/*.py
```
