# Contributing

Bug reports and portability fixes are welcome. Before opening a change:

1. Run `./scripts/validate.sh`.
2. Run `./install.sh --dry-run --full`.
3. Do not include account state, tokens, browser profiles, wallpaper collections
   or machine-specific absolute home paths.
4. Keep the public monitor configuration portable.
5. Credit upstream code and preserve its license notice.

For installer bugs, include the distribution, GPU family, Hyprland version and
the exact failing step. Remove usernames, tokens and private paths from logs.

Sparrow Shell is opinionated. Changes that preserve the coherent visual system
and improve portability are a better fit than adding many optional themes.
