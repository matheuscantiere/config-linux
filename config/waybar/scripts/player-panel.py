#!/usr/bin/env python3
"""Painel de midia flutuante no estilo do widget expandido do iOS.

Capa circular, titulo/artista, barra de progresso com tempo decorrido e
restante, controles anterior/play/proxima e slider de volume.
Controla o Spotify via playerctl e o volume via wpctl (PipeWire).
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")

import hashlib
import os
import re
import shutil
import signal
import subprocess
import time
import urllib.request
from pathlib import Path

from gi.repository import Adw, Gdk, GLib, Gtk

PLAYER = "spotify"

# Geometria da ilha real na Waybar, medida na tela: o card recolhido tem que
# pousar exatamente em cima dela, nao virar uma segunda pilula abaixo.
ILHA_W, ILHA_H = 231, 30
ILHA_TOPO = 3      # y da pilula dentro da barra
ILHA_DX = -11      # a ilha nao fica no centro exato do monitor
CARD_W, CARD_H = 560, 371
# O card aberto ocupa a janela inteira: assim o retangulo desfocado que o
# Hyprland desenha atras dela coincide com o card, sem faixa sobrando.
CARD_TOPO = 0
JANELA_H = CARD_H
ART_DIR = Path.home() / ".cache" / "waybar" / "art"
POLL_MS = 400

CSS = b"""
window, window.background {
  background-color: transparent;
}

#card {
  background-color: #0a0a0a;
  border-radius: 28px;
}

#conteudo {
  padding: 26px 30px;
}

scrolledwindow, scrolledwindow > viewport {
  background: none;
  border: none;
}

#art {
  border-radius: 999px;
  background-color: #1a1a1a;
}

#source {
  color: alpha(#ffffff, 0.55);
  font-size: 13px;
}

#title {
  color: #ffffff;
  font-size: 17px;
  font-weight: 700;
}

#subtitle {
  color: alpha(#ffffff, 0.55);
  font-size: 14px;
}

#elapsed, #remaining {
  color: alpha(#ffffff, 0.5);
  font-size: 12px;
  font-weight: 700;
}

#airplay {
  color: alpha(#ffffff, 0.85);
  font-size: 26px;
  background: none;
  border: none;
  box-shadow: none;
  padding: 0;
  min-width: 40px;
  min-height: 40px;
}

#airplay:hover {
  color: #ffffff;
}

button.transport {
  color: #ffffff;
  background: none;
  border: none;
  box-shadow: none;
  padding: 0 10px;
  min-width: 56px;
  min-height: 56px;
  font-size: 30px;
  transition: opacity 150ms ease;
  opacity: 0.92;
}

button.transport:hover { opacity: 1; }
button.transport:active { opacity: 0.6; }

button.play { font-size: 40px; min-width: 76px; }

/* sliders: trilha fina arredondada, preenchimento branco */
scale trough {
  background-color: alpha(#ffffff, 0.28);
  min-height: 6px;
  border-radius: 999px;
}

/* seletor completo: o tema define a cor de acento com especificidade maior */
scale > trough > highlight,
scale > trough > fill {
  background-color: #ffffff;
  background-image: none;
  border: none;
  border-radius: 999px;
  min-width: 0px;
  min-height: 0px;
}

/* barra de progresso sem botao, como na referencia */
#progress slider {
  min-width: 0px;
  min-height: 0px;
  background: none;
  border: none;
  box-shadow: none;
  margin: 0px;
  opacity: 0;
}

#progress trough {
  min-height: 5px;
}

#volume slider {
  background-color: #ffffff;
  border-radius: 999px;
  min-width: 22px;
  min-height: 22px;
  margin: -9px;
  box-shadow: 0 1px 3px alpha(#000000, 0.5);
  border: none;
}

#vol-low, #vol-high {
  color: alpha(#ffffff, 0.8);
  font-size: 18px;
}
"""


def run(args):
    try:
        return subprocess.run(
            args, capture_output=True, text=True, timeout=2
        ).stdout.strip()
    except Exception:
        return ""


def playerctl(*args):
    return run(["playerctl", f"--player={PLAYER}", *args])


def desenha_triangulo(cr, x, y, altura, direcao):
    """Triangulo isosceles apontando para a esquerda (-1) ou direita (+1)."""
    meia = altura / 2
    largura = altura * 0.86
    cr.move_to(x, y - meia)
    cr.line_to(x + largura * direcao, y)
    cr.line_to(x, y + meia)
    cr.close_path()


def finaliza(cr, raio):
    """Preenche a figura com canto arredondado, como os simbolos do iOS."""
    cr.set_source_rgb(1, 1, 1)
    cr.set_line_join(1)   # ROUND
    cr.set_line_cap(1)
    cr.set_line_width(raio * 2)
    cr.stroke_preserve()
    cr.fill()


def icone_play(_area, cr, w, h, *_a):
    lado = h * 0.58
    largura = lado * 0.86
    # O triangulo cresce de x para x+largura: recuar meia largura o centraliza.
    desenha_triangulo(cr, w / 2 - largura / 2, h / 2, lado, 1)
    finaliza(cr, h * 0.035)


def icone_pause(_area, cr, w, h, *_a):
    lado = h * 0.58
    largura = lado * 0.30
    vao = lado * 0.26
    for sinal in (-1, 1):
        x = w / 2 + sinal * (vao / 2 + largura / 2) - largura / 2
        cr.rectangle(x, h / 2 - lado / 2, largura, lado)
    finaliza(cr, h * 0.035)


def icone_passo(direcao):
    """Duas setas lado a lado: anterior (-1) ou proxima (+1)."""

    def desenha(_area, cr, w, h, *_a):
        raio = h * 0.03
        lado = h * 0.46
        largura = lado * 0.86
        vao = largura * 0.10
        total = 2 * largura + vao

        # Desenha sempre apontando para a direita num sistema centrado e
        # espelha no eixo X para a versao "anterior". Sem isso a figura fica
        # deslocada meia seta para um lado e encosta na borda.
        cr.save()
        cr.translate(w / 2, h / 2)
        cr.scale(direcao, 1)
        cr.translate(-total / 2, 0)
        desenha_triangulo(cr, 0, 0, lado, 1)
        desenha_triangulo(cr, largura + vao, 0, lado, 1)
        cr.restore()

        finaliza(cr, raio)

    return desenha


def botao_icone(desenho, tamanho, acao):
    area = Gtk.DrawingArea()
    area.set_content_width(tamanho)
    area.set_content_height(tamanho)
    area.set_draw_func(desenho)

    botao = Gtk.Button()
    botao.set_child(area)
    botao.add_css_class("transport")
    botao.set_cursor_from_name("pointer")
    botao.connect("clicked", lambda *_: acao())
    botao.area = area
    return botao


def saidas_audio():
    """Lista de (id, nome) das saidas disponiveis, na ordem do wpctl."""
    texto = run(["wpctl", "status"])
    itens = []
    dentro = False
    for linha in texto.splitlines():
        if "Sinks:" in linha:
            dentro = True
            continue
        if dentro:
            # a secao acaba na proxima categoria ("Sources:", "Filters:", ...)
            if re.search(r"\b(Sources|Filters|Streams)\b", linha):
                break
            m = re.search(r"(\d+)\.\s+(.*?)\s*\[vol", linha)
            if m:
                itens.append((m.group(1), m.group(2).strip()))
    return itens


def saida_atual():
    """Nome da saida padrao. O id de @DEFAULT_AUDIO_SINK@ nao bate com o id
    listado pelo wpctl status, entao a comparacao e pelo nome."""
    for linha in run(["wpctl", "inspect", "@DEFAULT_AUDIO_SINK@"]).splitlines():
        m = re.search(r'node\.description = "(.*)"', linha)
        if m:
            return m.group(1)
    return ""


def mmss(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


class Panel(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_decorated(False)
        self.set_default_size(CARD_W, JANELA_H)
        self.set_resizable(False)

        self.art_key = None
        self.duration = 0
        self.seeking = False
        self.volume_held = False

        self.build()
        self.refresh()

        self.aplica_progresso(0.0)
        GLib.timeout_add(POLL_MS, self.refresh)

        esc = Gtk.EventControllerKey()
        esc.connect("key-pressed", self.on_key)
        self.add_controller(esc)

        # Fecha ao perder o foco, como um popover. So passa a valer depois que
        # a janela recebeu foco uma vez: recem-aberta ela ainda nao e ativa e
        # se fecharia sozinha.
        # A Waybar fecha o painel com SIGUSR1 para a animacao de recolher
        # rodar; SIGTERM mataria a janela de uma vez.
        GLib.unix_signal_add(
            GLib.PRIORITY_DEFAULT, signal.SIGUSR1, self.fecha_animado
        )
        GLib.unix_signal_add(
            GLib.PRIORITY_DEFAULT, signal.SIGUSR2, self.mostra
        )

        self.ja_focou = False
        # PANEL_NO_AUTOCLOSE=1 mantem o painel aberto (util para depurar)
        if os.environ.get("PANEL_NO_AUTOCLOSE") != "1" and \
                os.environ.get("PANEL_HOVER") != "1":
            self.connect("notify::is-active", self.on_focus)

    def on_focus(self, *_a):
        if self.is_active():
            self.ja_focou = True
            return
        if self.ja_focou:
            GLib.timeout_add(150, self.close_if_unfocused)

    def close_if_unfocused(self):
        if not self.is_active():
            self.fecha_animado()
        return False

    # ---------- construcao ----------

    def build(self):
        # A janela e transparente e do tamanho final. Dentro dela, o "card"
        # cresce do tamanho da ilha fechada ate o tamanho cheio.
        # Gtk.Fixed para poder posicionar o card livremente: ao recolher ele
        # sobe ate a faixa da barra, onde some atras dela, dando a impressao
        # de virar a propria ilha.
        raiz = Gtk.Fixed()
        raiz.set_size_request(CARD_W, JANELA_H)
        self.raiz = raiz
        self.set_child(raiz)

        self.card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.card.set_name("card")
        self.card.set_overflow(Gtk.Overflow.HIDDEN)
        self.card.set_size_request(ILHA_W, ILHA_H)
        # Sem ancorar, a caixa raiz estica o card ate o tamanho todo e a
        # animacao some.
        raiz.put(self.card, (CARD_W - ILHA_W) / 2 + ILHA_DX, ILHA_TOPO)

        # ScrolledWindow com politica EXTERNAL: deixa o card encolher abaixo do
        # tamanho minimo do conteudo e recortar o excesso. Sem isso o conteudo
        # empurraria o card para o tamanho cheio e nao haveria animacao.
        clip = Gtk.ScrolledWindow()
        clip.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.EXTERNAL)
        clip.set_propagate_natural_width(False)
        clip.set_propagate_natural_height(False)
        clip.set_vexpand(True)
        clip.set_hexpand(True)
        self.card.append(clip)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.set_name("conteudo")
        card.set_size_request(CARD_W, CARD_H)
        card.set_opacity(0.0)
        self.conteudo = card
        clip.set_child(card)

        # linha de cima: capa + textos + airplay
        topo = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        card.append(topo)

        self.art = Gtk.Picture()
        self.art.set_name("art")
        self.art.set_size_request(104, 104)
        self.art.set_content_fit(Gtk.ContentFit.COVER)
        self.art.set_overflow(Gtk.Overflow.HIDDEN)
        topo.append(self.art)

        textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        textos.set_valign(Gtk.Align.CENTER)
        textos.set_hexpand(True)
        topo.append(textos)

        self.source = Gtk.Label(xalign=0, label="Spotify")
        self.source.set_name("source")
        textos.append(self.source)

        self.title = Gtk.Label(xalign=0, label="—")
        self.title.set_name("title")
        self.title.set_ellipsize(3)  # END
        self.title.set_max_width_chars(28)
        textos.append(self.title)

        self.subtitle = Gtk.Label(xalign=0, label="")
        self.subtitle.set_name("subtitle")
        self.subtitle.set_ellipsize(3)
        self.subtitle.set_max_width_chars(32)
        textos.append(self.subtitle)

        self.saida = Gtk.Button(label="󰋋")
        self.saida.set_name("airplay")
        self.saida.set_valign(Gtk.Align.CENTER)
        self.saida.set_cursor_from_name("pointer")
        self.saida.set_has_tooltip(True)
        self.saida.connect("clicked", self.proxima_saida)
        # Sao 6 saidas nesta maquina; ciclar ate achar a certa e chato, entao
        # o botao direito abre o seletor completo.
        direito = Gtk.GestureClick.new()
        direito.set_button(3)
        direito.connect("pressed", lambda *_: subprocess.Popen(["pavucontrol"]))
        self.saida.add_controller(direito)
        topo.append(self.saida)

        # progresso
        self.progress = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 1000, 1
        )
        self.progress.set_name("progress")
        self.progress.set_draw_value(False)
        self.progress.set_margin_top(30)
        self.progress.set_cursor_from_name("pointer")
        self.progress.connect("change-value", self.on_seek)
        card.append(self.progress)

        tempos = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        tempos.set_margin_top(2)
        card.append(tempos)

        self.elapsed = Gtk.Label(xalign=0, label="0:00")
        self.elapsed.set_name("elapsed")
        self.elapsed.set_hexpand(True)
        tempos.append(self.elapsed)

        self.remaining = Gtk.Label(xalign=1, label="-0:00")
        self.remaining.set_name("remaining")
        tempos.append(self.remaining)

        # controles
        controles = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=26)
        controles.set_halign(Gtk.Align.CENTER)
        controles.set_margin_top(18)
        card.append(controles)

        prev = botao_icone(icone_passo(-1), 46, lambda: self.acao("previous"))
        controles.append(prev)

        self.tocando = False
        self.play = botao_icone(self.icone_estado, 58, lambda: self.acao("play-pause"))
        self.play.add_css_class("play")
        controles.append(self.play)

        nxt = botao_icone(icone_passo(1), 46, lambda: self.acao("next"))
        controles.append(nxt)

        # volume
        vol_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        vol_row.set_margin_top(22)
        card.append(vol_row)

        low = Gtk.Label(label="󰕿")
        low.set_name("vol-low")
        vol_row.append(low)

        self.volume = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 100, 1
        )
        self.volume.set_name("volume")
        self.volume.set_draw_value(False)
        self.volume.set_hexpand(True)
        self.volume.set_cursor_from_name("pointer")
        self.volume.connect("change-value", self.on_volume)
        vol_row.append(self.volume)

        high = Gtk.Label(label="󰕾")
        high.set_name("vol-high")
        vol_row.append(high)

    def icone_estado(self, area, cr, w, h, *a):
        if self.tocando:
            icone_pause(area, cr, w, h, *a)
        else:
            icone_play(area, cr, w, h, *a)

    # ---------- acoes ----------

    # ---------- animacao de expansao ----------

    def aplica_progresso(self, t):
        """t=0: a ilha na barra. t=1: card inteiro embaixo dela."""
        w = ILHA_W + (CARD_W - ILHA_W) * t
        h = ILHA_H + (CARD_H - ILHA_H) * t
        self.card.set_size_request(int(w), int(h))

        # Posicao acompanha o tamanho: recolhido pousa sobre a ilha, aberto
        # fica centralizado logo abaixo da barra.
        x = (CARD_W - w) / 2 + ILHA_DX * (1 - t)
        y = ILHA_TOPO + (CARD_TOPO - ILHA_TOPO) * t
        self.raiz.move(self.card, x, y)
        if os.environ.get("PANEL_DEBUG") == "1":
            print(f"{time.monotonic():.3f} t={t:.3f} w={w:.0f} h={h:.0f}", flush=True)
        # Perto de t=0 o card e uma pilula preta vazia exatamente sobre a ilha
        # real. Se ele aparecesse opaco ali, se veria uma "ilha sem conteudo"
        # piscando antes da janela sumir. Entao ele se dissolve no fim, deixando
        # a ilha de verdade aparecer por baixo.
        self.card.set_opacity(max(0.0, min(1.0, t / 0.22)))
        # O conteudo so aparece depois que o card ja abriu um pedaco, senao
        # ele surge espremido dentro da pilula.
        self.conteudo.set_opacity(max(0.0, min(1.0, (t - 0.05) / 0.35)))

    def expande(self, de, para, ao_terminar=None):
        alvo = Adw.CallbackAnimationTarget.new(self.aplica_progresso)
        # Mola em vez de curva fixa: e o que da a sensacao do iOS.
        rigidez = 20.0 if os.environ.get("PANEL_ANIM_SLOW") == "1" else 320.0
        mola = Adw.SpringParams.new(0.92, 1.0, rigidez)
        self.anim = Adw.SpringAnimation.new(self, de, para, mola, alvo)
        self.anim.set_epsilon(0.002)
        if ao_terminar:
            self.anim.connect("done", lambda *_: ao_terminar())
        self.anim.play()

    def fecha_animado(self, *_a):
        if getattr(self, "fechando", False) or not self.get_visible():
            return GLib.SOURCE_CONTINUE
        self.fechando = True
        self.expande(1.0, 0.0, self.esconde)
        return GLib.SOURCE_CONTINUE

    def esconde(self):
        self.set_visible(False)
        self.fechando = False
        self.ja_focou = False

    def mostra(self, *_a):
        """Abre o painel. O processo ja esta de pe, entao nao ha espera de
        partida do GTK: o primeiro quadro ja e a pilula fechada."""
        if self.get_visible():
            return GLib.SOURCE_CONTINUE
        self.fechando = False
        self.refresh()
        self.aplica_progresso(0.0)
        self.present()
        # Mapear a janela custa ~100ms de quadros engasgados. Se a mola comecar
        # ai, o relogio dela corre nesse intervalo e o primeiro quadro visivel
        # ja aparece com a animacao pela metade. Entao espera alguns quadros
        # seguidos e rapidos antes de soltar a mola.
        relogio = self.get_frame_clock()
        if relogio is None:
            self.expande(0.0, 1.0)
            return GLib.SOURCE_CONTINUE

        self._pinturas = 0
        self._ultima_pintura = 0.0
        relogio.begin_updating()   # forca quadros mesmo sem nada sujo

        def quadro(*_a):
            agora = time.monotonic()
            intervalo = agora - self._ultima_pintura
            self._ultima_pintura = agora
            # so conta quadros em cadencia normal (< 25ms): os do mapeamento
            # chegam espacados e nao valem
            self._pinturas = self._pinturas + 1 if intervalo < 0.025 else 0
            if self._pinturas < 2:
                return
            relogio.disconnect(self._sinal_pintura)
            self._sinal_pintura = None
            relogio.end_updating()
            self.expande(0.0, 1.0)

        self._sinal_pintura = relogio.connect("after-paint", quadro)
        # Rede de seguranca: se os quadros nunca estabilizarem, anima assim mesmo.
        GLib.timeout_add(250, self._solta_mola)
        return GLib.SOURCE_CONTINUE

    def _solta_mola(self):
        if getattr(self, "_sinal_pintura", None) is not None:
            relogio = self.get_frame_clock()
            if relogio is not None:
                try:
                    relogio.disconnect(self._sinal_pintura)
                    relogio.end_updating()
                except Exception:
                    pass
            self._sinal_pintura = None
            self.expande(0.0, 1.0)
        return False

    def on_key(self, _c, keyval, *_a):
        if keyval == Gdk.KEY_Escape:
            self.fecha_animado()
            return True
        if keyval == Gdk.KEY_space:
            self.acao("play-pause")
            return True
        return False

    def acao(self, cmd):
        playerctl(cmd)
        GLib.timeout_add(120, self.refresh)

    def proxima_saida(self, *_a):
        lista = saidas_audio()
        if not lista:
            return
        atual = saida_atual()
        indice = next((i for i, (_id, nome) in enumerate(lista) if nome == atual), -1)
        alvo = lista[(indice + 1) % len(lista)]
        run(["wpctl", "set-default", alvo[0]])
        self.atualiza_saida()

    def atualiza_saida(self):
        nome = saida_atual() or "desconhecida"
        lista = saidas_audio()
        if len(lista) > 1:
            nome = f"{nome}\n\nClique para trocar ({len(lista)} saidas)"
        self.saida.set_tooltip_text(nome)

    def on_seek(self, _s, _scroll, value):
        if self.duration > 0:
            alvo = max(0, min(self.duration, self.duration * value / 1000))
            playerctl("position", f"{alvo:.1f}")
        return False

    def on_volume(self, _s, _scroll, value):
        value = max(0, min(100, value))
        run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{value / 100:.2f}"])
        return False

    # ---------- estado ----------

    def carrega_capa(self, url):
        if not url or url == self.art_key:
            return
        self.art_key = url
        nome = hashlib.md5(url.encode()).hexdigest()[:12] + ".jpg"
        destino = ART_DIR / nome
        if not destino.exists():
            ART_DIR.mkdir(parents=True, exist_ok=True)
            try:
                with urllib.request.urlopen(url, timeout=6) as r, open(
                    destino, "wb"
                ) as f:
                    shutil.copyfileobj(r, f)
            except Exception:
                return
        self.art.set_filename(str(destino))

    def refresh(self):
        dados = playerctl(
            "metadata",
            "--format",
            "{{status}}|{{title}}|{{artist}}|{{album}}|{{position}}|{{mpris:length}}|{{mpris:artUrl}}",
        )
        campos = dados.split("|") if dados else []
        if len(campos) < 7:
            self.title.set_text("Nada tocando")
            self.subtitle.set_text("")
            self.tocando = False
            self.play.area.queue_draw()
            return True

        status, titulo, artista, album, pos_us, dur_us, art_url = campos[:7]

        self.title.set_text(titulo or "—")
        self.subtitle.set_text(" - ".join(x for x in (artista, album) if x))
        self.tocando = status == "Playing"
        self.play.area.queue_draw()
        self.carrega_capa(art_url)

        pos = int(pos_us or 0) / 1_000_000
        self.duration = int(dur_us or 0) / 1_000_000
        if self.duration > 0:
            self.progress.set_value(pos / self.duration * 1000)
            self.elapsed.set_text(mmss(pos))
            self.remaining.set_text("-" + mmss(self.duration - pos))

        self.atualiza_saida()

        vol = run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
        m = re.search(r"([\d.]+)", vol)
        if m and not self.volume.has_focus():
            self.volume.set_value(float(m.group(1)) * 100)

        return True


PIDFILE = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "player-panel.pid"


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="dev.local.playerpanel")

    def do_activate(self):
        css = Gtk.CssProvider()
        css.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self.painel = Panel(self)

        # Residente: a janela so aparece com SIGUSR2. Manter o processo de pe
        # elimina os ~400ms de partida do Python/GTK, que era o que engolia o
        # comeco da animacao de abertura.
        self.hold()
        PIDFILE.write_text(str(os.getpid()))

        if os.environ.get("PANEL_ABRIR_JA") == "1":
            self.painel.mostra()


if __name__ == "__main__":
    try:
        App().run(None)
    finally:
        try:
            if PIDFILE.exists() and PIDFILE.read_text().strip() == str(os.getpid()):
                PIDFILE.unlink()
        except Exception:
            pass
