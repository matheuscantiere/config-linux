# config-linux

Personal Linux configuration: Hyprland (Wayland) desktop on Ubuntu, with Fish, Kitty,
Neovim, Waybar and Rofi. Catppuccin Macchiato throughout.

## Layout

| Path | Installs to | Contents |
|---|---|---|
| `config/` | `~/.config/` | Per-application configuration |
| `home/` | `~/` | Shell dotfiles (`.bashrc`, `.profile`, `.zshrc`), `.gitconfig`, `.npmrc` |
| `local/bin/` | `~/.local/bin/` | Custom scripts (`ccbrain`, `img2logo`) |
| `packages/` | — | Snapshot of manually installed apt packages |

### Applications covered

`hypr` (Hyprland, hyprlock, hyprpaper, helper scripts, wallpapers) · `waybar` ·
`rofi` · `kitty` · `fish` · `nvim` · `fastfetch` · `neofetch` · `azote` ·
`vicinae` · `git` · `gtk-3.0`

## Install

```bash
git clone <this-repo> ~/github/config-linux
cd ~/github/config-linux
./install.sh
```

`install.sh` symlinks every tracked path into place. Anything already present is
moved to `<name>.bak-<timestamp>` first, so nothing is overwritten silently.

Dependencies for the Hyprland setup are installed by `config/hypr/install-deps.sh`.
The apt package snapshot can be replayed with:

```bash
xargs -a packages/apt-manual.txt sudo apt install -y
```

## Updating the snapshot

Because the files are symlinked, edits made to the live configuration land
directly in this repository. Commit them as usual.

Refresh the package list with:

```bash
apt-mark showmanual | sort > packages/apt-manual.txt
```

## Not tracked

Machine-local state and credentials are excluded: `fish_variables`, session
restore files, `~/.git-credentials`, `~/.claude.json`, and any `*.bak`/`*.orig`
files. See `.gitignore`.
