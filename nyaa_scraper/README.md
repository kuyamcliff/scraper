# nyaa-scraper 2.0 — Ultimate Release Intelligence Engine

This version replaces the prototype's regex-only matching and arbitrary global quality score with a layered system:

- Contextual anime filename parsing via `aniparse` plus deterministic enrichment/fallback parsing.
- Canonical AniList identity, title aliases and paginated season retrieval.
- Absolute episode, season/episode, ranges, specials, movies, OVA/ONA and batch awareness.
- Hard eligibility gates before ranking: wrong series/season/episode, unwanted codecs, bad groups, extras, unknown resolution and other policy violations do not get rescued by positive scores.
- Explainable scoring with match, source, resolution, codec, audio, subtitle, release-group, size, availability, version, curated and preference components.
- Streaming, archival, mobile and maximum profiles plus custom JSON policy overrides.
- Deterministic multi-query / multi-page Nyaa discovery with deduplication and mirror health tracking.
- Persistent SQLite state for RSS so restarts do not forget processed releases.
- Retry/partial failure handling and challenge/schema detection rather than treating blocked pages as empty search results.
- Safe media-server rename planning with collision detection and no internal AniList IDs polluting filenames.
- Typed normalized models and a large offline regression suite covering ambiguous anime titles and real-world naming styles.

## Commands

`nyaa-scraper search "Attack on Titan" --season 3 --episode 1 --resolution 1080p`

`nyaa-scraper search "One Piece" --absolute 1136 --profile maximum`

`nyaa-scraper search "Frieren" --profile archival --json-out`

`nyaa-scraper id 16498 --season 3 --resolution 1080p`

## Design notes

Quality is not the same thing as resolution or codec. A 2160p label is not automatically better than a native, well-encoded 1080p source, and modern codecs are preferences rather than universal quality multipliers. The policy engine therefore separates hard eligibility from soft ranking.

The project is intentionally source-adapter based at the data-model level so additional release providers and curated release intelligence can be added without rewriting matching logic.
