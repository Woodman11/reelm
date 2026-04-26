#!/usr/bin/env python3
"""
Search your saved YouTube videos by keyword.

Usage:
  python3 search.py "proxmox vlan"
  python3 search.py "veeam backup" --open       # opens top result in browser
  python3 search.py --list                       # list all saved videos
"""

import os
import sqlite3
import subprocess
import sys

from paths import DB_PATH


def db():
    if not os.path.exists(DB_PATH):
        print("No database found. Save a video first with Option+Y.")
        sys.exit(1)
    return sqlite3.connect(DB_PATH)


def search(query):
    conn = db()
    # FTS5: multi-word = AND, "phrase" = exact phrase, term* = prefix
    rows = conn.execute('''
        SELECT v.title, s.video_id, s.start_secs
        FROM segments s
        JOIN videos v ON v.id = s.video_id
        WHERE segments MATCH ?
        ORDER BY rank
        LIMIT 25
    ''', (query,)).fetchall()
    conn.close()
    return rows


def list_videos():
    conn = db()
    rows = conn.execute('''
        SELECT id, title, save_ts_secs, has_transcript, indexed_at
        FROM videos
        ORDER BY indexed_at DESC
    ''').fetchall()
    conn.close()
    return rows


def fmt_time(secs):
    m, s = divmod(int(secs), 60)
    h, m = divmod(m, 60)
    if h:
        return f'{h}:{m:02d}:{s:02d}'
    return f'{m}:{s:02d}'


def yt_url(video_id, start_secs):
    return f'https://youtube.com/watch?v={video_id}&t={start_secs}'


if __name__ == '__main__':
    args = sys.argv[1:]

    if not args or '--help' in args:
        print(__doc__)
        sys.exit(0)

    if '--list' in args:
        videos = list_videos()
        if not videos:
            print("No saved videos yet.")
        else:
            print(f"\n{'':>4}  {'Title':<55} {'Transcript':>10}  Saved at")
            print('-' * 85)
            for vid_id, title, save_ts, has_tr, _ in videos:
                tr = 'yes' if has_tr else 'no '
                print(f"       {title[:55]:<55}  {tr:>10}  {fmt_time(save_ts)}")
                print(f"       https://youtube.com/watch?v={vid_id}\n")
        sys.exit(0)

    open_top = '--open' in args
    query_parts = [a for a in args if not a.startswith('--')]
    if not query_parts:
        print("Provide a search query.")
        sys.exit(1)

    query = ' '.join(query_parts)
    try:
        results = search(query)
    except Exception as e:
        print(f"Search error: {e}")
        sys.exit(1)

    if not results:
        print(f'No results for: "{query}"')
        sys.exit(0)

    print(f'\n{len(results)} result(s) for "{query}":\n')
    for i, (title, vid_id, start) in enumerate(results, 1):
        url = yt_url(vid_id, start)
        print(f'  {i:>2}. [{fmt_time(start)}] {title}')
        print(f'      {url}\n')

    if open_top:
        url = yt_url(results[0][1], results[0][2])
        print(f'Opening: {url}')
        subprocess.run(['open', url])
