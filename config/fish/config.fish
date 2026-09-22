set -g fish_greeting

function fish_greeting
    neofetch
    set_color FF8000
    echo '                                   مرحبا بالعالم'
    set_color normal
end

set -gx EDITOR nvim
set -gx VISUAL nvim

# Created by `pipx` on 2025-02-06 18:20:55
set PATH $PATH /home/matheus/.local/bin

zoxide init fish | source
alias cd="z"

# ccbrain — Second Brain + Claude Code
set -gx SECOND_BRAIN_VAULT /home/mcantiere/private-second-brain/vault
fish_add_path /home/mcantiere/.local/bin
