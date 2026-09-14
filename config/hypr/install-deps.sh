#!/usr/bin/env bash
# Installs every package the Hyprland config references on Ubuntu 26.04.
# All package names were verified against apt before this script was written.

set -euo pipefail

PKGS=(
    waybar                  # status bar
    rofi                    # app launcher and clipboard picker
    thunar                  # file manager ($fileManager)
    cliphist                # clipboard history
    wl-clipboard            # wl-copy / wl-paste
    grim slurp              # screenshots
    nwg-bar                 # power menu (SUPER+ESCAPE)
    hyprpaper               # wallpaper daemon (swww is not packaged for Ubuntu)
    hyprpolkitagent         # polkit authentication agent
    brightnessctl           # screen brightness without root
    pavucontrol             # audio mixer (right-click the waybar volume module)
    network-manager-gnome   # nm-connection-editor (click the waybar network module)
    papirus-icon-theme      # icons for rofi
)

sudo apt-get update
sudo apt-get install -y "${PKGS[@]}"

# brightnessctl needs the user in these groups to write brightness without root.
sudo usermod -aG video,input "$USER" || true

systemctl --user daemon-reload || true

echo
echo "Done. Log out and back in so the new groups apply, then reload Hyprland:"
echo "    hyprctl reload"
