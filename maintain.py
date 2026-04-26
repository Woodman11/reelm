#!/usr/bin/env python3
"""
DB maintenance: retry failed transcripts, optimize FTS5 index, vacuum.
Safe to run while server.py is also running.
"""

import glob
import os
import shutil
import sqlite3
import subprocess
import tempfile
import json
from datetime import datetime

from paths import DB_PATH

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'maintain.log')
SERVER_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'server.log')
LOG_ROTATE_BYTES = 1_000_000  # 1 MB
LOG_KEEP_TAIL_LINES = 200


def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    with open(LOG_PATH, 'a') as f:
        f.write(line + '\n')


def _resolve_ytdlp():
    # launchctl's PATH excludes homebrew dirs, so shutil.which alone fails under LaunchAgents.
    for candidate in (shutil.which('yt-dlp'), '/opt/homebrew/bin/yt-dlp', '/usr/local/bin/yt-dlp'):
        if candidate and os.path.exists(candidate):
            return candidate
    raise RuntimeError("yt-dlp not found — install with `brew install yt-dlp`")


def _fetch_segments(video_id):
    ytdlp = _resolve_ytdlp()
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            [
                ytdlp,
                '--write-auto-subs',
                '--sub-lang', 'en',
                '--sub-format', 'json3',
                '--skip-download',
                '--no-playlist',
                '-q',
                '-o', os.path.join(tmpdir, '%(id)s'),
                f'https://www.youtube.com/watch?v={video_id}',
            ],
            capture_output=True, timeout=60
        )
        files = glob.glob(os.path.join(tmpdir, f'{video_id}.*.json3'))
        if not files:
            return None
        with open(files[0]) as f:
            data = json.load(f)
    segments = []
    for event in data.get('events', []):
        if 'segs' not in event:
            continue
        start = event.get('tStartMs', 0) / 1000
        text = ''.join(s.get('utf8', '') for s in event['segs']).strip()
        if text and text != '\n':
            segments.append((start, text))
    return segments or None


def retry_missing_transcripts(conn):
    rows = conn.execute(
        'SELECT id, title FROM videos WHERE has_transcript=0'
    ).fetchall()

    if not rows:
        log("Retry: no videos missing transcripts")
        return

    log(f"Retry: {len(rows)} video(s) with no transcript")
    retried = 0

    for video_id, title in rows:
        try:
            segments = _fetch_segments(video_id)
            if not segments:
                log(f"  FAIL {video_id} — {title}: no subtitles available")
                continue
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


def rotate_log(path):
    try:
        size = os.path.getsize(path)
    except FileNotFoundError:
        return
    if size < LOG_ROTATE_BYTES:
        return
    # Truncate-in-place: launchd opens server.log with O_APPEND so it keeps writing
    # cleanly after the truncate. Preserve the last N lines for context.
    with open(path, 'rb') as f:
        f.seek(max(0, size - 256_000))
        tail_lines = f.read().splitlines()[-LOG_KEEP_TAIL_LINES:]
    with open(path, 'wb') as f:
        f.write(b'--- log rotated by maintain.py ---\n')
        f.write(b'\n'.join(tail_lines))
        f.write(b'\n')
    log(f"Rotated {os.path.basename(path)} (was {size // 1024} KB)")


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
    rotate_log(SERVER_LOG_PATH)
    rotate_log(LOG_PATH)

    conn.close()
    log("=== maintenance done ===")
