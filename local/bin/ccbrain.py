#!/usr/bin/env python3
"""
ccbrain — Second Brain search wrapper para Claude Code
Uso: ccbrain "sua pergunta ou tarefa"
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

# ─── CONFIG ───────────────────────────────────────────────────────────────────

VAULT_PATH = Path(os.environ.get("SECOND_BRAIN_VAULT", "~/private-second-brain/vault")).expanduser()

# Prioridade de pastas (hub-first)
PRIORITY_FOLDERS = [
    "02-shared-context",   # context hub principal
    "00-standards",        # padrões de código e arquitetura
    "01-projects",         # projetos ativos
    "98-guides",           # guias
    "03-inbox",            # inbox / em processamento
    "99-templates",        # templates
]

# Máximo de notas injetadas no contexto
MAX_NOTES = 5
MAX_LINES_PER_NOTE = 80

# ─── FUNÇÕES ──────────────────────────────────────────────────────────────────

def check_vault():
    if not VAULT_PATH.exists():
        print(f"[ccbrain] ⚠️  Vault não encontrado em: {VAULT_PATH}")
        print(f"[ccbrain] Defina SECOND_BRAIN_VAULT=/caminho/do/vault ou ajuste o script.")
        return False
    return True


def search_vault(query: str) -> list[Path]:
    """Busca ripgrep no vault, retorna lista de arquivos ordenados por relevância."""

    if not check_vault():
        return []

    terms = [t for t in query.split() if len(t) > 3]

    found_files: dict[Path, int] = {}

    for term in terms:
        try:
            result = subprocess.run(
                ["rg", "-i", "-l", "--glob", "*.md", term, str(VAULT_PATH)],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.strip().split("\n"):
                if line:
                    p = Path(line)
                    found_files[p] = found_files.get(p, 0) + 1
        except (subprocess.TimeoutExpired, FileNotFoundError):
            try:
                result = subprocess.run(
                    ["grep", "-r", "-i", "-l", term, str(VAULT_PATH)],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.strip().split("\n"):
                    if line:
                        p = Path(line)
                        found_files[p] = found_files.get(p, 0) + 1
            except subprocess.TimeoutExpired:
                pass

    # Boost para arquivos em pastas prioritárias
    scored = []
    for path, score in found_files.items():
        folder_score = 0
        for i, folder in enumerate(PRIORITY_FOLDERS):
            if folder in str(path):
                folder_score = len(PRIORITY_FOLDERS) - i
                break
        if _is_active(path):
            folder_score += 2
        scored.append((path, score + folder_score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in scored[:MAX_NOTES]]


def _is_active(path: Path) -> bool:
    """Verifica rápido se nota tem status: active no frontmatter."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i > 15:
                    break
                if "active" in line or "processado" in line:
                    return True
    except Exception:
        pass
    return False


def read_note(path: Path) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()[:MAX_LINES_PER_NOTE]
            return "".join(lines)
    except Exception:
        return ""


def read_index() -> str:
    """Inclui o hub principal de contexto compartilhado."""
    index = VAULT_PATH / "02-shared-context" / "index-shared-context.md"
    if index.exists():
        return read_note(index)
    # fallback para qualquer index na raiz
    for candidate in VAULT_PATH.glob("**/index*.md"):
        return read_note(candidate)
    return ""


def build_context(query: str) -> str:
    context_parts = []

    index_content = read_index()
    if index_content:
        context_parts.append(f"=== SECOND BRAIN — index-shared-context.md ===\n{index_content}")

    relevant_files = search_vault(query)

    for path in relevant_files:
        if path.name == "index-shared-context.md":
            continue
        content = read_note(path)
        if content:
            rel = path.relative_to(VAULT_PATH)
            context_parts.append(f"=== SECOND BRAIN — {rel} ===\n{content}")

    if not context_parts:
        return ""

    found_count = len(relevant_files)
    header = f"[ccbrain] {found_count} nota(s) encontrada(s) no vault\n\n"
    return header + "\n\n".join(context_parts)


def run_claude(query: str, context: str):
    if context:
        full_prompt = f"""Contexto do Second Brain (vault Obsidian):

{context}

---

Tarefa/Pergunta:
{query}

Instruções:
- Use o contexto do second brain acima como referência
- Se o contexto não for suficiente, diga explicitamente o que falta
"""
    else:
        full_prompt = query

    os.execvp("claude", ["claude", full_prompt])


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ccbrain — Second Brain wrapper para Claude Code"
    )
    parser.add_argument("query", nargs="+", help="Pergunta ou tarefa")
    parser.add_argument(
        "--dry-run", "-d", action="store_true",
        help="Mostra o contexto sem chamar o Claude"
    )
    parser.add_argument(
        "--vault", "-v",
        help="Path do vault (override de SECOND_BRAIN_VAULT)"
    )

    args = parser.parse_args()

    if args.vault:
        global VAULT_PATH
        VAULT_PATH = Path(args.vault).expanduser()

    query = " ".join(args.query)

    print(f"[ccbrain] Buscando no vault: {VAULT_PATH}", file=sys.stderr)

    context = build_context(query)

    if args.dry_run:
        print("=== CONTEXTO QUE SERIA INJETADO ===")
        print(context or "(vault não encontrado ou sem resultados)")
        return

    run_claude(query, context)


if __name__ == "__main__":
    main()
