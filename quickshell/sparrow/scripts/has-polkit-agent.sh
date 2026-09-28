#!/usr/bin/env bash
set -euo pipefail

# Exit 1 to make systemd skip Sparrow's agent when a known alternative is
# already running for this user. Fail open if pgrep is unavailable: missing
# an authentication UI is worse than attempting to start the selected agent.
command -v pgrep >/dev/null 2>&1 || exit 0

uid="$(id -u)"
agent_pattern='(^|/)(lxqt-policykit-agent|polkit-gnome-authentication-agent-1|polkit-mate-authentication-agent-1|polkit-kde-authentication-agent-1|hyprpolkitagent)([[:space:]]|$)'

if pgrep --uid "$uid" --full "$agent_pattern" >/dev/null 2>&1; then
    exit 1
fi

exit 0
