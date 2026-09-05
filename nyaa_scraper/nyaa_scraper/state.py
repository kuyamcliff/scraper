from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional


class StateStore:
    def __init__(self, path: str | Path = "nyaa_scraper_state.db"):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS seen_release (
            source TEXT NOT NULL,
            release_key TEXT NOT NULL,
            first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
            processed INTEGER NOT NULL DEFAULT 0,
            matched INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(source, release_key)
        );
        CREATE TABLE IF NOT EXISTS library_item (
            media_key TEXT NOT NULL,
            episode_key TEXT NOT NULL,
            info_hash TEXT,
            quality_score REAL,
            filename TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(media_key, episode_key)
        );
        """)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def seen(self, source: str, key: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM seen_release WHERE source=? AND release_key=?", (source, key)).fetchone()
        return row is not None

    def mark_seen(self, source: str, key: str, *, processed: bool = False, matched: bool = False) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO seen_release(source, release_key, processed, matched) VALUES(?,?,?,?)",
            (source, key, int(processed), int(matched)),
        )
        if processed or matched:
            self.conn.execute(
                "UPDATE seen_release SET processed=MAX(processed,?), matched=MAX(matched,?) WHERE source=? AND release_key=?",
                (int(processed), int(matched), source, key),
            )
        self.conn.commit()

    def upsert_library_item(self, media_key: str, episode_key: str, info_hash: Optional[str], quality_score: float, filename: str) -> None:
        self.conn.execute("""
            INSERT INTO library_item(media_key, episode_key, info_hash, quality_score, filename)
            VALUES(?,?,?,?,?)
            ON CONFLICT(media_key, episode_key) DO UPDATE SET
                info_hash=excluded.info_hash,
                quality_score=excluded.quality_score,
                filename=excluded.filename,
                updated_at=CURRENT_TIMESTAMP
        """, (media_key, episode_key, info_hash, quality_score, filename))
        self.conn.commit()
