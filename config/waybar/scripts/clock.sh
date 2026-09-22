#!/bin/sh
# Waybar clock: texto = HH:MM · DD mes (pt-BR).
# Tooltip = data por extenso + card da faixa do Spotify (Pango markup).

ACENTO='#df6124'
FRACO='#8a8073'
BARRA_LARGURA=22

pango() {  # escapa markup nos campos vindos do player
  printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'
}

json() {   # escapa para string JSON, quebras reais viram \n
  printf '%s' "$1" \
    | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' \
    | awk '{ printf "%s%s", (NR > 1 ? "\\n" : ""), $0 }'
}

mmss() {   # segundos -> M:SS
  s=${1%%.*}
  [ -z "$s" ] && s=0
  printf '%d:%02d' $((s / 60)) $((s % 60))
}

corta() {  # trunca texto longo com reticencias
  printf '%s' "$1" | awk -v n="$2" \
    '{ if (length($0) > n) print substr($0, 1, n - 1) "…"; else print $0 }'
}

texto=$(LC_ALL=C date +'%H:%M · %d %b' | sed \
  -e 's/Jan/jan/' -e 's/Feb/fev/' -e 's/Mar/mar/' -e 's/Apr/abr/' \
  -e 's/May/mai/' -e 's/Jun/jun/' -e 's/Jul/jul/' -e 's/Aug/ago/' \
  -e 's/Sep/set/' -e 's/Oct/out/' -e 's/Nov/nov/' -e 's/Dec/dez/')

dia=$(LC_ALL=C date +'%A, %d/%m/%Y' | sed \
  -e 's/Monday/segunda-feira/'   -e 's/Tuesday/terca-feira/' \
  -e 's/Wednesday/quarta-feira/' -e 's/Thursday/quinta-feira/' \
  -e 's/Friday/sexta-feira/'     -e 's/Saturday/sabado/' \
  -e 's/Sunday/domingo/')

tooltip="<b>$dia</b>"

status=$(playerctl --player=spotify status 2>/dev/null)
case "$status" in
  Playing) icone="󰎈" ;;
  Paused)  icone="󰏤" ;;
  *)       icone="" ;;
esac

if [ -n "$icone" ]; then
  titulo=$(pango "$(corta "$(playerctl --player=spotify metadata title 2>/dev/null)" 34)")
  artista=$(pango "$(corta "$(playerctl --player=spotify metadata artist 2>/dev/null)" 34)")
  album=$(pango "$(corta "$(playerctl --player=spotify metadata album 2>/dev/null)" 34)")

  pos=$(playerctl --player=spotify position 2>/dev/null)
  dur_us=$(playerctl --player=spotify metadata mpris:length 2>/dev/null)
  dur=$((${dur_us:-0} / 1000000))

  # Barra de progresso: parte tocada no acento, resto apagado.
  cheio=0
  [ "$dur" -gt 0 ] && cheio=$(awk -v p="${pos:-0}" -v d="$dur" -v n="$BARRA_LARGURA" \
      'BEGIN { v = int(p / d * n); print (v < 0 ? 0 : (v > n ? n : v)) }')
  vazio=$((BARRA_LARGURA - cheio))
  tocado=$(awk -v n="$cheio" 'BEGIN { while (i++ < n) printf "━" }')
  resto=$(awk  -v n="$vazio" 'BEGIN { while (i++ < n) printf "━" }')

  tooltip=$(printf '%s\n<span foreground="%s">%s</span>' \
    "$tooltip" "$FRACO" "$(awk -v n=28 'BEGIN { while (i++ < n) printf "─" }')")
  tooltip=$(printf '%s\n\n<span foreground="%s" size="large">%s</span>  <b>%s</b>' \
    "$tooltip" "$ACENTO" "$icone" "$titulo")
  [ -n "$artista" ] && tooltip=$(printf '%s\n<span foreground="%s">     %s</span>' \
    "$tooltip" "$ACENTO" "$artista")
  [ -n "$album" ] && tooltip=$(printf '%s\n<span foreground="%s" size="small"><i>     %s</i></span>' \
    "$tooltip" "$FRACO" "$album")

  if [ "$dur" -gt 0 ]; then
    tooltip=$(printf '%s\n\n<span foreground="%s">%s</span><span foreground="%s">%s</span>' \
      "$tooltip" "$ACENTO" "$tocado" "$FRACO" "$resto")
    tooltip=$(printf '%s\n<span foreground="%s" size="small">%s%s%s</span>' \
      "$tooltip" "$FRACO" "$(mmss "$pos")" \
      "$(awk -v n=14 'BEGIN { while (i++ < n) printf " " }')" "$(mmss "$dur")")
  fi
fi

printf '{"text":"%s","tooltip":"%s"}\n' "$(json "$texto")" "$(json "$tooltip")"
