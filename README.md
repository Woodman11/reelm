# Reelm

Save YouTube videos with **Shift+Y** while watching, then search across the
auto-generated transcripts of every video you've saved. Local SQLite + FTS5,
no cloud.

<!-- DEMO: drop the recorded screencast at assets/demo.gif (or .mp4) and
     uncomment the block below. Recommended: 30s, 640×400, ~10fps GIF
     (under ~5MB) showing: save with Shift+Y → search popup → click result
     → YouTube jumps to the spoken-word timestamp.
<p align="center">
  <img src="assets/demo.gif" alt="Reelm demo: save a YouTube video with Shift+Y, search across saved transcripts, jump to the spoken word" width="640">
</p>
-->

```
[Chrome extension] --Shift+Y--> [localhost:7799 server] --> videos.db (FTS5)
                                        |
                                        +-- yt-dlp (transcript fallback)
```

## Install (macOS, recommended — Homebrew)

If you don't already have [Homebrew](https://brew.sh) installed:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Then:

```bash
brew tap Woodman11/reelm
brew install reelm
brew services start reelm
```

Then load the Chrome extension (one-time, manual — not yet on the Web Store):

1. Open `chrome://extensions`
2. Enable **Developer mode** (top right)
3. Click **Load unpacked** → select `$(brew --prefix)/opt/reelm/libexec/extension`
   (or copy the path from the `Chrome extension` caveat shown after `brew install`)
4. Pin the icon if you want the popup search

Open any YouTube video and press **Shift+Y** — a toast confirms the save
and the transcript indexes in the background.

### What to expect on first run

- macOS may prompt you to allow Python to accept incoming network connections
  the first time the server binds. The server only listens on `127.0.0.1`,
  so denying the prompt won't break anything — Allow is fine either way.
- Chrome will show a "Disable developer mode extensions" banner each time
  you launch the browser. That's expected for unpacked extensions and will
  go away once we publish to the Web Store.
- The first save on a new YouTube tab may trigger a one-time Private Network
  Access prompt — accept it.

### Privacy / data location

Everything stays on your Mac:

- **Database:** `~/Library/Application Support/Reelm/videos.db`
  (titles, video IDs, save timestamps, full auto-generated transcripts).
  Older `~/Library/Application Support/MyYouTubeSearch/` DBs are migrated
  automatically on first run.
- **Logs:** `$(brew --prefix)/var/log/reelm/`
- **No network egress** beyond `youtube.com` (for transcript fetches) and
  the local server on `127.0.0.1:7799`.

To wipe everything:

```bash
brew services stop reelm
brew uninstall reelm
rm -rf ~/Library/Application\ Support/Reelm
```

## Install (developer / from source)

For working on the code directly:

```bash
brew install python yt-dlp
git clone https://github.com/Woodman11/reelm ~/reelm
cd ~/reelm
./setup.sh
venv/bin/python server.py
```

Then load the extension as above, pointing at `~/reelm/extension`.

### (Optional) Dev auto-start at login

Two LaunchAgent plists are included for source installs:

- `com.james.reelm.plist` — runs `server.py` continuously
- `com.james.reelm-maintain.plist` — runs `maintain.py` every 15 min
  to retry failed transcripts and optimize the FTS index

**Both plists are user-specific.** Before installing, edit them:

- Change the `Label` (`com.james.…`) to your own prefix
- Replace `/Users/james/Systems-Admin/youtube-search/` with the actual
  install path

Then:

```bash
cp com.*.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.<you>.reelm.plist
launchctl load ~/Library/LaunchAgents/com.<you>.reelm-maintain.plist
```

(Brew users skip this whole section — `brew services` handles it.)

## Usage

- **Save a video:** Shift+Y on any `youtube.com/watch?v=…` page
- **Search:** click the extension icon → type a query
- **CLI search:** `venv/bin/python search.py "your query"`
- **Maintenance run:** `venv/bin/python maintain.py`

## Files

| File | Purpose |
|------|---------|
| `server.py` | HTTP server on `localhost:7799`, accepts saves, indexes transcripts |
| `maintain.py` | Retries failed transcripts, optimizes FTS5, vacuums |
| `app.py` | Optional menu-bar wrapper around `server.py` (uses `rumps`) |
| `search.py` | CLI search |
| `extension/` | Chrome MV3 extension (manifest, content/background/popup scripts) |
| `videos.db` | SQLite DB (created on first run, gitignored) |
| `setup.sh` | Creates venv, installs deps |
| `build.sh` | Builds standalone `.app` via PyInstaller (optional) |

## Migrating existing data

`videos.db` is gitignored. To copy your indexed library to a new Mac:

```bash
scp old-mac:~/reelm/videos.db ~/reelm/videos.db
```

## Troubleshooting

- **Toast says "Server not running"** → start `server.py`, or check
  `~/Library/LaunchAgents/` is loaded (`launchctl list | grep reelm`)
- **Saves work but transcripts never index** → verify `yt-dlp` is on PATH
  (`which yt-dlp`) and is recent (`yt-dlp --version` ≥ 2026.03.17)
- **Shift+Y does nothing** → reload the YouTube tab after installing the
  extension
