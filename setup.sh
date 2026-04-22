#!/bin/bash
set -e

echo "==> Checking Python 3..."
if ! command -v python3 &>/dev/null; then
  echo "ERROR: Python 3 is required. Install it from https://www.python.org/downloads/"
  exit 1
fi

echo "==> Creating virtual environment..."
python3 -m venv venv

echo "==> Installing dependencies (this may take a few minutes — Whisper pulls in PyTorch)..."
venv/bin/pip install --upgrade pip -q
venv/bin/pip install -r requirements.txt

echo ""
echo "==> Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Start the server:       venv/bin/python server.py"
echo "  2. Load the extension in Chrome:"
echo "       - Go to chrome://extensions"
echo "       - Enable Developer mode (top right)"
echo "       - Click 'Load unpacked' and select the 'extension/' folder"
echo "  3. Open a YouTube video and press Shift+Y to save it"
echo ""
echo "To have the server start automatically at login, run:"
echo "  cp com.james.youtube-search.plist ~/Library/LaunchAgents/"
echo "  launchctl load ~/Library/LaunchAgents/com.james.youtube-search.plist"
