#!/usr/bin/env bash
# Prints the currently playing track for the hyprlock "current song" label.
# Stays silent when playerctl is missing or nothing is playing.

command -v playerctl >/dev/null 2>&1 || exit 0

status=$(playerctl status 2>/dev/null) || exit 0
[ "$status" = "Playing" ] || [ "$status" = "Paused" ] || exit 0

artist=$(playerctl metadata artist 2>/dev/null)
title=$(playerctl metadata title 2>/dev/null)

[ -n "$title" ] || exit 0

if [ -n "$artist" ]; then
    printf '󰝚  %s — %s\n' "$artist" "$title"
else
    printf '󰝚  %s\n' "$title"
fi
