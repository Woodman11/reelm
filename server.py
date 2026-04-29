#!/usr/bin/env python3
"""
YouTube Search Server — listens on localhost:7799
Receives save requests from the Chrome extension,
fetches transcripts, and indexes them in SQLite FTS5.
"""

import glob
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from paths import DB_PATH

PORT = 7799


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS videos (
            id            TEXT PRIMARY KEY,
            title         TEXT,
            save_ts_secs  INTEGER,
            indexed_at    INTEGER DEFAULT (strftime('%s','now')),
            has_transcript INTEGER DEFAULT 0
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS segments USING fts5(
            video_id      UNINDEXED,
            start_secs    UNINDEXED,
            text,
            tokenize      = "porter unicode61"
        );
    ''')
    conn.commit()
    conn.close()


def _write_segments(video_id, segments):
    """Insert (start_secs, text) pairs and mark has_transcript=1."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('UPDATE videos SET has_transcript=1 WHERE id=?', (video_id,))
    for start, text in segments:
        conn.execute(
            'INSERT INTO segments(video_id, start_secs, text) VALUES (?,?,?)',
            (video_id, int(start), text)
        )
    conn.commit()
    conn.close()


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


def fetch_and_index(video_id, title, save_ts_secs):
    try:
        segments = _fetch_segments(video_id)
        if segments:
            _write_segments(video_id, segments)
            print(f"Indexed {len(segments)} segments: {title}")
        else:
            print(f"No transcript for {video_id}: {title}")
    except Exception as e:
        print(f"Transcript unavailable for {video_id}: {e}")


class Handler(BaseHTTPRequestHandler):

    def _allowed_origin(self):
        origin = self.headers.get('Origin', '')
        return origin if origin.startswith('chrome-extension://') else None

    def _cors(self):
        origin = self._allowed_origin()
        if not origin:
            return
        self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Vary', 'Origin')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Private-Network', 'true')

    def _origin_ok(self):
        # Browser-originated requests must come from a chrome-extension:// origin.
        # CLI/loopback callers (curl, search.py) send no Origin header and are allowed.
        origin = self.headers.get('Origin')
        return origin is None or origin.startswith('chrome-extension://')

    def do_OPTIONS(self):
        if not self._origin_ok():
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if not self._origin_ok():
            self.send_response(403)
            self.end_headers()
            return
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)

        if parsed.path == '/stats':
            conn = sqlite3.connect(DB_PATH)
            row = conn.execute(
                'SELECT COUNT(*), SUM(has_transcript) FROM videos'
            ).fetchone()
            conn.close()
            self._reply(200, {'total': row[0], 'indexed': row[1] or 0})
            return

        if parsed.path != '/search':
            self.send_response(404)
            self.end_headers()
            return
        q = parse_qs(parsed.query).get('q', [''])[0].strip()
        if not q:
            self._reply(400, {'results': [], 'error': 'Missing query'})
            return
        try:
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute('''
                SELECT v.title, s.video_id, s.start_secs, v.indexed_at
                FROM segments s
                JOIN videos v ON v.id = s.video_id
                WHERE segments MATCH ?
                ORDER BY v.indexed_at DESC
                LIMIT 25
            ''', (q,)).fetchall()
            conn.close()
            results = [
                {
                    'title': title,
                    'videoId': vid_id,
                    'startSecs': start,
                    'savedAt': indexed_at,
                    'url': f'https://youtube.com/watch?v={vid_id}&t={start}'
                }
                for title, vid_id, start, indexed_at in rows
            ]
            self._reply(200, {'results': results})
        except Exception as e:
            self._reply(500, {'results': [], 'error': str(e)})

    def do_POST(self):
        if not self._origin_ok():
            self.send_response(403)
            self.end_headers()
            return
        length = int(self.headers.get('Content-Length', 0))
        data = json.loads(self.rfile.read(length))

        if self.path == '/transcript':
            video_id = data.get('videoId', '').strip()
            segments = data.get('segments') or []
            if video_id and segments:
                conn = sqlite3.connect(DB_PATH)
                row = conn.execute(
                    'SELECT has_transcript FROM videos WHERE id=?', (video_id,)
                ).fetchone()
                conn.close()
                if row and not row[0]:
                    pairs = [(s['start'], s['text']) for s in segments if s.get('text')]
                    _write_segments(video_id, pairs)
                    print(f"Transcript from browser: {video_id} ({len(pairs)} segs)")
            self._reply(200, {'ok': True})
            return

        if self.path == '/wipe':
            from datetime import datetime
            backup = DB_PATH.replace('.db', f'.backup-{datetime.now().strftime("%Y%m%d-%H%M%S")}.db')
            shutil.copy2(DB_PATH, backup)
            conn = sqlite3.connect(DB_PATH)
            deleted = conn.execute('SELECT COUNT(*) FROM videos').fetchone()[0]
            conn.execute('DELETE FROM segments')
            conn.execute('DELETE FROM videos')
            conn.commit()
            conn.close()
            # VACUUM cannot run inside a transaction — open a fresh autocommit connection.
            vac = sqlite3.connect(DB_PATH, isolation_level=None)
            vac.execute('VACUUM')
            vac.close()
            print(f"Wiped {deleted} videos — backup at {backup}")
            self._reply(200, {'deleted': deleted})
            return

        if self.path != '/save':
            self.send_response(404)
            self.end_headers()
            return

        video_id = data.get('videoId', '').strip()
        title = data.get('title', 'Unknown').strip()
        save_ts_secs = int(data.get('currentTime', 0))

        if not video_id:
            self._reply(400, {'message': 'Missing videoId'})
            return

        conn = sqlite3.connect(DB_PATH)
        exists = conn.execute(
            'SELECT id FROM videos WHERE id=?', (video_id,)
        ).fetchone()
        conn.close()

        if exists:
            mins, secs = divmod(save_ts_secs, 60)
            msg = f'Already saved — {title}'
            new_save = False
        else:
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                'INSERT INTO videos(id, title, save_ts_secs) VALUES (?,?,?)',
                (video_id, title, save_ts_secs)
            )
            conn.commit()
            conn.close()
            # Legacy yt-dlp fallback only if old extension (no segments key sent)
            if 'segments' not in data:
                threading.Thread(
                    target=fetch_and_index,
                    args=(video_id, title, save_ts_secs),
                    daemon=True
                ).start()

            mins, secs = divmod(save_ts_secs, 60)
            msg = f'Saved @ {mins}:{secs:02d} — {title}'
            new_save = True

        self._reply(200, {'message': msg, 'new_save': new_save})

    def _reply(self, code, body):
        payload = json.dumps(body).encode()
        self.send_response(code)
        self._cors()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(payload))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        pass  # silence default access log


if __name__ == '__main__':
    init_db()
    print(f'YouTube search server listening on http://localhost:{PORT}')
    print('Press Ctrl+C to stop.\n')
    HTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
