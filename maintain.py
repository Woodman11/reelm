#!/usr/bin/env python3
"""
DB maintenance: retry failed transcripts, optimize FTS5 index, vacuum.
Safe to run while server.py is also running.
"""

import os
import sqlite3
import sys
from datetime import datetime

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    HAS_TRANSCRIPT_API = True
except ImportError:
    HAS_TRANSCRIPT_API = False

if getattr(sys, 'frozen', False):
    _data_dir = os.path.expanduser('~/Library/Application Support/MyYouTubeSearch')
    DB_PATH = os.path.join(_data_dir, 'videos.db')
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'videos.db')

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'maintain.log')


def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    with open(LOG_PATH, 'a') as f:
        f.write(line + '\n')


def retry_missing_transcripts(conn):
    if not HAS_TRANSCRIPT_API:
        log("SKIP retry — youtube-transcript-api not installed")
        return

    rows = conn.execute(
        'SELECT id, title FROM videos WHERE has_transcript=0'
    ).fetchall()

    if not rows:
        log("Retry: no videos missing transcripts")
        return

    log(f"Retry: {len(rows)} video(s) with no transcript")
    api = YouTubeTranscriptApi()
    retried = 0

    for video_id, title in rows:
        try:
            transcript = api.fetch(video_id)
            segments = [(seg.start, seg.text) for seg in transcript]
            conn.execute('UPDATE videos SET has_transcript=1 WHERE id=?', (video_id,))
            for start, text in segments:
                conn.execute(
                    'INSERT INTO segments(video_id, start_secs, text) VALUES (?,?,?)',
                    (video_id, int(start), text)
                )
            conn.commit()
            log(f"  OK  {video_id} — {title} ({len(segments)} segments)")
            retried += 1
        except Exception as e:
            log(f"  FAIL {video_id} — {title}: {e}")

    log(f"Retry: recovered {retried}/{len(rows)}")


def optimize_fts(conn):
    conn.execute("INSERT INTO segments(segments) VALUES('optimize')")
    conn.commit()
    log("FTS5 optimize: done")


def vacuum(conn):
    conn.execute("VACUUM")
    log("VACUUM: done")


def stats(conn):
    total, indexed = conn.execute(
        'SELECT COUNT(*), SUM(has_transcript) FROM videos'
    ).fetchone()
    segs = conn.execute('SELECT COUNT(*) FROM segments').fetchone()[0]
    size_kb = os.path.getsize(DB_PATH) // 1024
    log(f"Stats: {total} videos ({indexed or 0} indexed, {total - (indexed or 0)} missing) | {segs} segments | {size_kb} KB")


if __name__ == '__main__':
    log("=== maintenance start ===")
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL')

    stats(conn)
    retry_missing_transcripts(conn)
    optimize_fts(conn)
    vacuum(conn)
    stats(conn)

    conn.close()
    log("=== maintenance done ===")
