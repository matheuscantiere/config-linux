#!/bin/sh
# Controla o painel de midia.
#   (sem argumento)   alterna
#   abrir [x]         abre, opcionalmente numa posicao X
#   fechar            fecha
#
# O painel e um processo residente: ele fica de pe com a janela escondida e
# so aparece com SIGUSR2. Iniciar o Python/GTK a cada abertura custava ~400ms
# e engolia o comeco da animacao.
CLASSE='dev.local.playerpanel'
LARGURA=560
TOPO=0           # a janela comeca no topo: o card sobe ate a barra ao recolher
PIDFILE="${XDG_RUNTIME_DIR:-/tmp}/player-panel.pid"
PAINEL="$HOME/.config/waybar/scripts/player-panel.py"

MODO=${1:-alternar}

vivo() {
  [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null
}

visivel() {
  hyprctl clients -j | grep -q "\"class\": \"$CLASSE\""
}

posiciona() {
  if [ -n "$1" ]; then
    ALVO_X=$1
  else
    set -- $(hyprctl monitors -j | python3 -c "
import json, sys
for m in json.load(sys.stdin):
    if m.get('focused'):
        print(m['x'], m['width'])
        break
")
    ALVO_X=$(( ${1:-0} + (${2:-1920} - LARGURA) / 2 ))
  fi

  i=0
  while [ "$i" -lt 100 ]; do
    if visivel; then
      hyprctl dispatch movewindowpixel \
        "exact $ALVO_X $TOPO,class:^(dev\.local\.playerpanel)$" >/dev/null
      break
    fi
    sleep 0.02
    i=$((i + 1))
  done
}

sobe_residente() {
  # PANEL_HOVER: quem fecha e o vigia de hover, nao a perda de foco.
  PANEL_HOVER=1 setsid python3 "$PAINEL" >/dev/null 2>&1 &
  i=0
  while [ "$i" -lt 150 ]; do
    vivo && return 0
    sleep 0.02
    i=$((i + 1))
  done
  return 1
}

abrir() {
  vivo || sobe_residente || exit 1
  kill -USR2 "$(cat "$PIDFILE")" 2>/dev/null
  posiciona "$1"
}

fechar() {
  vivo && kill -USR1 "$(cat "$PIDFILE")" 2>/dev/null
}

case "$MODO" in
  abrir)  visivel || abrir "$2" ;;
  fechar) fechar ;;
  *)      if visivel; then fechar; else abrir "$2"; fi ;;
esac
