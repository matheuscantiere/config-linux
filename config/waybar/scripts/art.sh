#!/bin/sh
# Capa do album: so reporta se deve aparecer. O download e o CSS ficam
# com o island.sh, que ja tem os metadados.
ART_DIR="$HOME/.cache/waybar/art"

if [ "$(cat "$ART_DIR/state" 2>/dev/null)" = "on" ] && [ -s "$HOME/.config/waybar/art.css" ]; then
  printf '{"text":" ","class":"on","tooltip":false}\n'
else
  printf '{"text":"","class":"off","tooltip":false}\n'
fi
