#!/bin/sh
# Alimenta as 5 barras do equalizador da ilha.
#
# Um unico cava; para cada quadro escreve uma linha JSON por barra num arquivo
# proprio. Os modulos da Waybar so fazem "tail -F" nesses arquivos: nao ha
# polling nem processo de shell por barra, quem acorda os modulos e o inotify
# do tail. Varios "tail" podem seguir o mesmo arquivo sem disputar linhas, o
# que um FIFO nao permitiria (a Waybar cria um modulo por monitor).

DIR="${XDG_RUNTIME_DIR:-/tmp}/waybar-eq"
CONF="$HOME/.config/waybar/cava-island.conf"
LIMPA_A_CADA=4000

mkdir -p "$DIR"

# Uma so instancia.
exec 9> "$DIR/lock"
if command -v flock >/dev/null 2>&1; then
  flock -n 9 || exit 0
fi

PIPE="$DIR/pipe"
rm -f "$PIPE"
mkfifo "$PIPE" || exit 1

limpa() {
  # Sem isso o cava vira orfao quando o driver morre e vai se acumulando a
  # cada reinicio da barra.
  [ -n "$CAVA_PID" ] && kill "$CAVA_PID" 2>/dev/null
  rm -f "$PIPE" "$DIR"/[1-5]
}
trap 'limpa; exit 0' EXIT INT TERM HUP

for i in 1 2 3 4 5; do
  : > "$DIR/$i"
done

while :; do
  cava -p "$CONF" > "$PIPE" 2>/dev/null &
  CAVA_PID=$!

  n=0
  while IFS=';' read -r b1 b2 b3 b4 b5 _; do
    printf '{"text":" ","class":"h%s"}\n' "${b1:-0}" >> "$DIR/1"
    printf '{"text":" ","class":"h%s"}\n' "${b2:-0}" >> "$DIR/2"
    printf '{"text":" ","class":"h%s"}\n' "${b3:-0}" >> "$DIR/3"
    printf '{"text":" ","class":"h%s"}\n' "${b4:-0}" >> "$DIR/4"
    printf '{"text":" ","class":"h%s"}\n' "${b5:-0}" >> "$DIR/5"

    n=$((n + 1))
    if [ "$n" -ge "$LIMPA_A_CADA" ]; then
      # Truncar e seguro: o "tail -F" detecta e volta ao inicio, que estara
      # vazio. Nao ha replay de quadros velhos.
      for i in 1 2 3 4 5; do : > "$DIR/$i"; done
      n=0
    fi
  done < "$PIPE"

  kill "$CAVA_PID" 2>/dev/null
  sleep 2   # cava caiu (troca de sink, por exemplo): tenta de novo
done
