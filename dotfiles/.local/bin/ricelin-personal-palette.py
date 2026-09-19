#!/usr/bin/env python3
import json
from pathlib import Path

home = Path.home()
cache = home / ".cache/ricelin"
colors = json.loads((cache / "colors.json").read_text())
palette = {}
for line in (cache / "ghostty-colors").read_text().splitlines():
    if line.startswith("palette = "):
        key, value = line.split("=", 2)[1:]
        palette[int(key)] = value.lstrip("#")

primary = colors["primary"].lstrip("#")
on_primary = colors["on_primary_container"].lstrip("#")
bg = palette.get(0, "14151a")
fg = palette.get(7, "a8aab1")
seg = colors["surface_container_highest"].lstrip("#")
seg_fg = colors["cream"].lstrip("#")

foot = ["[colors-dark]", "alpha=0.88", f"background={bg}", f"foreground={fg}", f"cursor={primary} {bg}", f"selection-background={palette.get(2, bg)}", f"selection-foreground={fg}"]
foot += [f"regular{i}={palette.get(i, fg)}" for i in range(8)]
bright = [fg, primary, on_primary, on_primary, primary, on_primary, primary, fg]
foot += [f"bright{i}={value}" for i, value in enumerate(bright)]
(cache / "foot-colors").write_text("\n".join(foot) + "\n")

starship = f'''add_newline = false
format = """
$cmd_duration $directory$git_branch
$character"""

[character]
success_symbol = "[ ](bold fg:{primary})"
error_symbol = "[ ](bold fg:{primary})"

[package]
disabled = true

[git_branch]
style = "bg:{seg}"
symbol = "󰘬"
truncation_length = 12
truncation_symbol = ""
format = " 󰜥 [](bold fg:{seg})[$symbol $branch(:$remote_branch)](fg:{seg_fg} bg:{seg})[ ](bold fg:{seg})"

[directory]
home_symbol = " "
read_only = "  "
style = "bg:{seg} fg:{seg_fg}"
truncation_length = 2
truncation_symbol = ".../"
format = '[](bold fg:{seg})[󰉋 → $path]($style)[](bold fg:{seg})'

[cmd_duration]
min_time = 0
format = '[](bold fg:{seg})[󰪢 $duration](bold bg:{seg} fg:{seg_fg})[](bold fg:{seg})'
'''

(home / ".config/starship.toml").write_text(starship)
(home / ".config/starship.toml").write_text(
    (home / ".local/share/ricelin-personal-addon/end4-starship.toml").read_text()
)
