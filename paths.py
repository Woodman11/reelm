"""Shared filesystem paths for youtube-search components."""
import os
import shutil

DATA_DIR = os.path.expanduser('~/Library/Application Support/MyYouTubeSearch')
DB_PATH = os.path.join(DATA_DIR, 'videos.db')


def _migrate_legacy_db():
    if os.path.exists(DB_PATH):
        return
    os.makedirs(DATA_DIR, exist_ok=True)
    legacy = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'videos.db')
    if os.path.exists(legacy):
        shutil.copy2(legacy, DB_PATH)


_migrate_legacy_db()
