#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

mkdir -p "$BIN_DIR" "$SYSTEMD_USER_DIR"

chmod +x "$REPO_DIR/cosmic_frequent_folders.py"
ln -sf "$REPO_DIR/cosmic_frequent_folders.py" "$BIN_DIR/cosmic-frequent-folders"

cp "$REPO_DIR/systemd/cosmic-frequent-folders.service" "$SYSTEMD_USER_DIR/"
cp "$REPO_DIR/systemd/cosmic-frequent-folders.timer" "$SYSTEMD_USER_DIR/"

systemctl --user daemon-reload
systemctl --user enable --now cosmic-frequent-folders.timer
systemctl --user start cosmic-frequent-folders.service

echo "Installation abgeschlossen. Timer Status:"
systemctl --user list-timers cosmic-frequent-folders.timer --no-pager
