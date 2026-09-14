#!/usr/bin/env bash
# Reports the number of upgradable apt packages in waybar JSON format.
# Prints nothing when the system is up to date, so the module stays hidden.
count=$(apt-get --just-print upgrade 2>/dev/null | grep -c '^Inst ')
[ "$count" -eq 0 ] && exit 0
printf '{"text":"%s","tooltip":"%s pacote(s) para atualizar","class":"has-updates"}\n' "$count" "$count"
