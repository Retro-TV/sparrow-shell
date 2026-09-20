fish_add_path -g "$HOME/.local/bin"

if type -q zoxide
    zoxide init fish | source
end
abbr -a ff fastfetch


if type -q starship
    starship init fish | source
end

function fish_greeting
end
