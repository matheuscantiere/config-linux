set fish_greeting


set_color blue
echo -n "           .             "
set_color white
echo " @helloworld"

set_color blue
echo -n "          .c.           "
set_color white
echo "┌───────────────────────────────┐"
set_color blue
echo "         .ccc.          │ OS : matheus                  │"
echo "        .lllll.         │ Kernel : 6.12.11-1-MANJARO    │"
echo "       ..;'olll.        │ WM : Hyprland                 │"
echo "      .dolllcccl.       │ Shell : fish                  │"
echo "     .lcc'   'ccc.      │ Ram: 16gb                     │"
echo "    .ccc'     'cc:.     │ CPU : i5-1235U                │"
echo "   .cccc'     'c:;..    └───────────────────────────────┘"
echo "  .\"'             '\".                                  "

set_color white
echo "                                   مرحبا بالعالم         "

set_color normal  # Reseta a cor para evitar erros depois




# Created by `pipx` on 2025-02-06 18:20:55
set PATH $PATH /home/matheus/.local/bin

zoxide init fish | source
alias cd="z"
