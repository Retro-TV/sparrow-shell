var groups = [
    { name: "Applications", items: [
        { id: "kitty", label: "Open Kitty", key: "Super+T" },
        { id: "thunar", label: "Open Thunar", key: "Super+E" },
        { id: "firefox", label: "Open Firefox", key: "Super+F" }
    ]},
    { name: "Sparrow", items: [
        { id: "lock", label: "Lock session", key: "Super+Alt+L" },
        { id: "screenshot", label: "Screenshot", key: "Super+Shift+S" },
        { id: "recorder", label: "Open Recorder", key: "Super+D" },
        { id: "launcher", label: "Open Launcher", key: "Super+Space" },
        { id: "wallpaper-picker", label: "Open Wallpaper Picker", key: "Super+C" },
        { id: "wallpaper-next", label: "Next Wallpaper", key: "Super+B" }
    ]},
    { name: "Audio and brightness", items: [
        { id: "volume-up", label: "Volume up", key: "XF86AudioRaiseVolume" },
        { id: "volume-down", label: "Volume down", key: "XF86AudioLowerVolume" },
        { id: "volume-mute", label: "Mute audio", key: "XF86AudioMute" },
        { id: "mic-mute", label: "Mute microphone", key: "XF86AudioMicMute" },
        { id: "brightness-up", label: "Brightness up", key: "XF86MonBrightnessUp" },
        { id: "brightness-down", label: "Brightness down", key: "XF86MonBrightnessDown" }
    ]},
    { name: "Workspaces", items: (function() {
        var out = [];
        for (var i = 1; i <= 9; i++) {
            out.push({ id: "workspace-" + i, label: "Focus workspace " + i, key: "Super+" + i });
            out.push({ id: "move-workspace-" + i, label: "Move window to workspace " + i, key: "Super+Shift+" + i });
        }
        return out;
    })()},
    { name: "Windows and layout", items: [
        { id: "close", label: "Close focused window", key: "Super+Q" },
        { id: "floating", label: "Toggle floating", key: "Super+W" },
        { id: "overview", label: "Toggle Overview", key: "Super+O" },
        { id: "focus-left", label: "Focus column left", key: "Super+Left" },
        { id: "focus-down", label: "Focus window below", key: "Super+Down" },
        { id: "focus-up", label: "Focus window above", key: "Super+Up" },
        { id: "focus-right", label: "Focus column right", key: "Super+Right" },
        { id: "move-column-left", label: "Move column left", key: "Super+Shift+Left" },
        { id: "move-column-right", label: "Move column right", key: "Super+Shift+Right" },
        { id: "move-window-down", label: "Move window down in column", key: "Super+Shift+Down" },
        { id: "move-window-up", label: "Move window up in column", key: "Super+Shift+Up" },
        { id: "consume-left", label: "Consume window from left", key: "Super+Ctrl+Left" },
        { id: "consume-right", label: "Consume window from right", key: "Super+Ctrl+Right" },
        { id: "tabbed", label: "Toggle tabbed column", key: "Super+Tab" },
        { id: "focus-floating-tiling", label: "Switch floating / tiled focus", key: "Super+V" },
        { id: "column-width", label: "Cycle column width", key: "Super+R" },
        { id: "window-height", label: "Cycle window height", key: "Super+Shift+R" },
        { id: "reset-height", label: "Reset window height", key: "Super+Ctrl+R" },
        { id: "maximize-column", label: "Maximize column", key: "Super+M" },
        { id: "fullscreen", label: "Toggle fullscreen", key: "Super+Shift+F" }
    ]},
    { name: "Session", items: [
        { id: "inhibit", label: "Toggle shortcut inhibition", key: "Super+Escape" }
    ]}
];

var entries = [];
for (var i = 0; i < groups.length; i++)
    for (var j = 0; j < groups[i].items.length; j++)
        entries.push(groups[i].items[j]);
