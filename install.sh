#!/usr/bin/env bash
# Symlink this repository's configuration into the current user's home.
# Existing targets are moved aside with a .bak-<timestamp> suffix.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"

backup_then_link() {
    local src="$1" dest="$2"
    if [ -e "$dest" ] || [ -L "$dest" ]; then
        if [ -L "$dest" ] && [ "$(readlink -f "$dest")" = "$(readlink -f "$src")" ]; then
            echo "ok       $dest"
            return
        fi
        mv "$dest" "$dest.bak-$STAMP"
        echo "backup   $dest -> $dest.bak-$STAMP"
    fi
    mkdir -p "$(dirname "$dest")"
    ln -s "$src" "$dest"
    echo "link     $dest"
}

# ~/.config/<app>
for dir in "$REPO_DIR"/config/*/; do
    backup_then_link "${dir%/}" "$HOME/.config/$(basename "$dir")"
done

# loose files inside ~/.config
for file in "$REPO_DIR"/config/*; do
    [ -f "$file" ] || continue
    backup_then_link "$file" "$HOME/.config/$(basename "$file")"
done

# home dotfiles
for file in "$REPO_DIR"/home/.*; do
    [ -f "$file" ] || continue
    backup_then_link "$file" "$HOME/$(basename "$file")"
done

# user scripts
for file in "$REPO_DIR"/local/bin/*; do
    [ -f "$file" ] || continue
    chmod +x "$file"
    backup_then_link "$file" "$HOME/.local/bin/$(basename "$file")"
done

echo
echo "Done. Restart Hyprland or run 'hyprctl reload' to apply the compositor config."
