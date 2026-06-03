# reeLm — Privacy Policy

_Last updated: 2026-04-27_

reeLm is a Chrome extension that saves YouTube videos you bookmark with **Shift+Y** and indexes their auto-generated transcripts so you can search across them later.

## What data is collected

When you press **Shift+Y** on a YouTube video, reeLm sends the video's **URL, title, and current playback timestamp** to a local server running on your own computer at `http://127.0.0.1:7799`. That server then fetches the video's auto-generated transcript from YouTube and stores it in a local SQLite database on your computer.

## Where the data goes

**Nowhere except your own computer.** Specifically:

- **Database:** `~/Library/Application Support/Reelm/videos.db` (macOS)
- **Logs:** `$(brew --prefix)/var/log/reelm/` (when installed via Homebrew)

No data is sent to reeLm's developer, to any analytics service, or to any third-party server. There is no telemetry, no account system, no cloud sync, and no advertising.

## Network access

reeLm makes network requests to two destinations only:

1. **`127.0.0.1:7799`** — the local server bundled with reeLm, running on your own machine.
2. **`youtube.com`** — to fetch transcripts via `yt-dlp` for videos you've explicitly saved.

## How to delete your data

Stop the server and remove the database:

```bash
brew services stop reelm
brew uninstall reelm
rm -rf ~/Library/Application\ Support/Reelm
```

Or simply delete `~/Library/Application Support/Reelm/videos.db` to wipe your saved-video index while keeping the extension installed.

## Contact

Source code: <https://github.com/Woodman11/reelm>

Issues and questions: <https://github.com/Woodman11/reelm/issues>

Chrome Web Store listing: <https://chromewebstore.google.com/detail/reelm/ldddhlkkgdipacjfljfjkkfhapkgfjkb>

## Credits

Extension icon: ["Search Video"](https://thenounproject.com/icon/4345473/) by [Injamamul hoq miraz](https://thenounproject.com/mirazhosen10/) from [The Noun Project](https://thenounproject.com), used under [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). Mirrored from the original.
