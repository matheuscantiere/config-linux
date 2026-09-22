#!/usr/bin/env python3
"""Abre e fecha o painel de midia conforme o mouse passa sobre a ilha.

A Waybar 0.15.0 nao tem evento de hover para modulos, entao a deteccao e feita
pela posicao do cursor, lida direto do socket IPC do Hyprland (sem "hyprctl",
que forkaria um processo a cada leitura).

Zona quente = a faixa da ilha no topo da tela. Enquanto o painel esta aberto a
zona passa a incluir o retangulo dele, para o mouse poder descer da barra ate
os controles sem que ele feche no meio do caminho.
"""

import os
import socket
import subprocess
import sys
import time

TOGGLE = os.path.expanduser("~/.config/waybar/scripts/player-panel-toggle.sh")

ILHA_LARGURA = 340   # faixa centrada que conta como "sobre a ilha"
BARRA_ALTURA = 34
PAINEL_W, PAINEL_H = 560, 371
PAINEL_TOPO = 0      # o painel aberto encosta no topo, cobrindo a ilha
PONTE = 0            # sem folga entre barra e painel: nao ha buraco no caminho

INTERVALO = 0.06     # ~16 leituras por segundo
CARENCIA_ABRIR = 0.18   # tempo parado sobre a ilha antes de abrir
CARENCIA_FECHAR = 0.45  # tempo fora da zona antes de fechar


def hypr_socket_path():
    his = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not his:
        return None
    base = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    caminho = f"{base}/hypr/{his}/.socket.sock"
    return caminho if os.path.exists(caminho) else None


def hypr(cmd, sock_path):
    """Uma requisicao no socket IPC. Conexao nova por chamada, sem fork."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(0.4)
            s.connect(sock_path)
            s.sendall(cmd.encode())
            partes = []
            while True:
                d = s.recv(8192)
                if not d:
                    break
                partes.append(d)
        return b"".join(partes).decode(errors="replace")
    except Exception:
        return ""


def cursor(sock_path):
    resposta = hypr("cursorpos", sock_path)
    try:
        x, y = resposta.strip().split(",")
        return int(x), int(y.strip())
    except Exception:
        return None


def monitores(sock_path):
    import json

    try:
        return json.loads(hypr("j/monitors", sock_path))
    except Exception:
        return []


def main():
    sock_path = hypr_socket_path()
    if not sock_path:
        print("HYPRLAND_INSTANCE_SIGNATURE ausente", file=sys.stderr)
        return 1

    mons = monitores(sock_path)
    if not mons:
        return 1

    aberto = False
    desde_dentro = None
    desde_fora = None
    painel_x = 0

    while True:
        time.sleep(INTERVALO)
        pos = cursor(sock_path)
        if pos is None:
            continue
        x, y = pos

        # Monitor sob o cursor.
        mon = next(
            (m for m in mons
             if m["x"] <= x < m["x"] + m["width"]
             and m["y"] <= y < m["y"] + m["height"]),
            None,
        )
        if mon is None:
            continue

        centro = mon["x"] + mon["width"] // 2
        alvo_x = centro - PAINEL_W // 2

        sobre_ilha = (
            mon["y"] <= y < mon["y"] + BARRA_ALTURA
            and abs(x - centro) <= ILHA_LARGURA // 2
        )

        sobre_painel = aberto and (
            painel_x <= x < painel_x + PAINEL_W
            and mon["y"] + PAINEL_TOPO - PONTE <= y
            < mon["y"] + PAINEL_TOPO + PAINEL_H
        )

        agora = time.monotonic()

        if sobre_ilha or sobre_painel:
            desde_fora = None
            if not aberto:
                desde_dentro = desde_dentro or agora
                if agora - desde_dentro >= CARENCIA_ABRIR:
                    painel_x = alvo_x
                    subprocess.Popen(
                        [TOGGLE, "abrir", str(alvo_x)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    aberto = True
                    desde_dentro = None
        else:
            desde_dentro = None
            if aberto:
                desde_fora = desde_fora or agora
                if agora - desde_fora >= CARENCIA_FECHAR:
                    subprocess.Popen(
                        [TOGGLE, "fechar"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    aberto = False
                    desde_fora = None


if __name__ == "__main__":
    sys.exit(main() or 0)
