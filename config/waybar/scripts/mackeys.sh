#!/usr/bin/env bash
# Alterna o teclado entre o layout normal e um layout "estilo macOS".
# No modo mac a tecla Super passa a emitir Ctrl (copiar = Super+C) e a tecla
# Ctrl passa a emitir Super, entao os binds $mainMod do Hyprland continuam
# acessiveis pela tecla Ctrl fisica.
#
# O estado vive no proprio Hyprland, nao em arquivo: um "hyprctl reload"
# restaura kb_options a partir do hyprland.conf e qualquer estado guardado
# em disco ficaria mentindo para a waybar.
set -euo pipefail

BASE_OPTS=""
MAC_OPTS="ctrl:swap_lwin_lctl"
MARKER="swap_lwin_lctl"
export MARKER
SIGNAL=8

# Lista o nome de cada teclado conhecido pelo compositor.
keyboards() {
    hyprctl devices -j | python3 -c \
        'import sys,json; [print(k["name"]) for k in json.load(sys.stdin).get("keyboards",[])]'
}

# O estado real e o do teclado principal, nao o valor global: ver apply().
is_on() {
    hyprctl devices -j | python3 -c \
        'import sys,json,os
m=os.environ["MARKER"]
ks=json.load(sys.stdin).get("keyboards",[])
main=[k for k in ks if k.get("main")] or ks
sys.exit(0 if main and m in (main[0].get("options") or "") else 1)'
}

apply() {
    # "hyprctl keyword input:kb_options" so alcanca teclados enumerados depois
    # da mudanca: um dispositivo ja conectado mantem as opcoes antigas. Por isso
    # cada teclado recebe a opcao explicitamente, alem do padrao global.
    hyprctl keyword input:kb_options "" >/dev/null
    [ -n "$1" ] && hyprctl keyword input:kb_options "$1" >/dev/null
    while IFS= read -r kb; do
        [ -n "$kb" ] || continue
        hyprctl keyword "device[$kb]:kb_options" "$1" >/dev/null 2>&1 || true
    done <<< "$(keyboards)"
    return 0
}

# Ajustes de bind por causa do swap de modificadores no modo mac:
#
# 1. O bindr de release em SUPER_L: no modo mac a tecla Ctrl fisica emite
#    Super_L, entao o menu abriria toda vez que um Ctrl fosse solto.
# 2. Binds globais selecionados devem ficar sempre na tecla Super fisica. No
#    modo normal ela emite Super; no modo mac, Ctrl.
# Binds que devem ficar sempre na mesma tecla fisica, a do logo Super. No modo
# normal ela emite Super; no modo mac emite Ctrl. Cada entrada e
# "modificador extra|tecla|dispatcher|argumento".
MAC_AWARE_BINDS="
|SPACE|exec|vicinae toggle
SHIFT|SPACE|exec|hyprctl switchxkblayout all next
SHIFT|S|exec|$HOME/.config/hypr/scripts/screenshot-area
|L|exec|hyprlock
|ESCAPE|exec|nwg-bar
|F2|exec|$HOME/.config/hypr/scripts/kbbacklight --dec
|F3|exec|$HOME/.config/hypr/scripts/kbbacklight --inc
"

# Fechar janela e abrir terminal ficam sempre nas mesmas teclas fisicas:
# Ctrl+Alt+Q e Ctrl+Alt+W. No modo normal isso e CONTROLALT. No modo mac a
# tecla Ctrl fisica emite Super, entao o mesmo combo vira ALT SUPER.
app_binds() {
    if [ "$1" = off ]; then
        hyprctl keyword unbind "CONTROLALT,Q" >/dev/null
        hyprctl keyword unbind "CONTROLALT,W" >/dev/null
        hyprctl keyword bind "ALT SUPER,Q,exec,kitty" >/dev/null
        hyprctl keyword bind "ALT SUPER,W,killactive," >/dev/null
    else
        hyprctl keyword unbind "ALT SUPER,Q" >/dev/null
        hyprctl keyword unbind "ALT SUPER,W" >/dev/null
        hyprctl keyword bind "CONTROLALT,Q,exec,kitty" >/dev/null
        hyprctl keyword bind "CONTROLALT,W,killactive," >/dev/null
    fi
}

physical_super_binds() {
    if [ "$1" = off ]; then from=SUPER; to=CTRL; else from=CTRL; to=SUPER; fi

    while IFS='|' read -r extra key disp arg; do
        [ -n "$key" ] || continue
        old_mod="$from"; new_mod="$to"
        [ -n "$extra" ] && { old_mod="$from $extra"; new_mod="$to $extra"; }
        hyprctl keyword unbind "$old_mod,$key" >/dev/null
        hyprctl keyword bind "$new_mod,$key,$disp,$arg" >/dev/null
    done <<< "$MAC_AWARE_BINDS"

    # O bindr de release em SUPER_L so existe no modo normal: no modo mac a
    # tecla Ctrl fisica emite Super_L e o menu abriria a cada Ctrl solto.
    if [ "$1" = off ]; then
        hyprctl keyword unbind "SUPER,SUPER_L" >/dev/null
    else
        hyprctl keyword bindr "SUPER,SUPER_L,exec,vicinae toggle" >/dev/null
    fi
}

# Abas do navegador. No modo normal um bind traduz Super+N em Ctrl+N. No modo
# mac a tecla Super ja emite Ctrl, entao o Firefox recebe Ctrl+N sozinho e
# manter o bind faria a tecla Ctrl fisica injetar um segundo combo por cima.
tab_binds() {
    for n in 1 2 3 4 5 6 7 8 9; do
        if [ "$1" = off ]; then
            hyprctl keyword unbind "SUPER,$n" >/dev/null
        else
            hyprctl keyword bind \
                "SUPER,$n,sendshortcut,CTRL,code:$((n + 9)),activewindow" >/dev/null
        fi
    done
}

if [ "${1:-status}" = "toggle" ]; then
    if is_on; then
        apply "$BASE_OPTS"
        physical_super_binds on
        app_binds on
        tab_binds on
    else
        apply "$MAC_OPTS"
        physical_super_binds off
        app_binds off
        tab_binds off
    fi
    pkill "-RTMIN+${SIGNAL}" waybar 2>/dev/null || true
fi

if is_on; then
    printf '{"text":"mac <span style=\x27italic\x27 weight=\x27900\x27 color=\x27#df6124\x27>on</span>","class":"on","tooltip":"Teclas estilo macOS ativas: Super+C / Super+V. A tecla Ctrl fisica virou Super."}\n'
else
    printf '{"text":"mac <span style=\x27italic\x27 weight=\x27900\x27 color=\x27#df6124\x27>off</span>","class":"off","tooltip":"Teclado no layout normal. Clique para ativar as teclas estilo macOS."}\n'
fi
