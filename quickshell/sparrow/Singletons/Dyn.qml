pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

/** Canonical Matugen semantic palette shared by the shell and palette consumers. */
Singleton {
    id: root

    readonly property string background: adapter.background
    readonly property string onBackground: adapter.on_background
    readonly property string surface: adapter.surface
    readonly property string onSurface: adapter.on_surface
    readonly property string onSurfaceVariant: adapter.on_surface_variant
    readonly property string surfaceDim: adapter.surface_dim
    readonly property string surfaceBright: adapter.surface_bright
    readonly property string surfaceContainerLowest: adapter.surface_container_lowest
    readonly property string surfaceContainer: adapter.surface_container
    readonly property string surfaceContainerLow: adapter.surface_container_low
    readonly property string surfaceContainerHigh: adapter.surface_container_high
    readonly property string surfaceContainerHighest: adapter.surface_container_highest
    readonly property string primary: adapter.primary
    readonly property string onPrimary: adapter.on_primary
    readonly property string primaryContainer: adapter.primary_container
    readonly property string onPrimaryContainer: adapter.on_primary_container
    readonly property string primaryFixed: adapter.primary_fixed
    readonly property string primaryFixedDim: adapter.primary_fixed_dim
    readonly property string secondary: adapter.secondary
    readonly property string onSecondary: adapter.on_secondary
    readonly property string secondaryContainer: adapter.secondary_container
    readonly property string onSecondaryContainer: adapter.on_secondary_container
    readonly property string tertiary: adapter.tertiary
    readonly property string onTertiary: adapter.on_tertiary
    readonly property string tertiaryContainer: adapter.tertiary_container
    readonly property string onTertiaryContainer: adapter.on_tertiary_container
    readonly property string error: adapter.error
    readonly property string onError: adapter.on_error
    readonly property string errorContainer: adapter.error_container
    readonly property string onErrorContainer: adapter.on_error_container
    readonly property string outline: adapter.outline
    readonly property string outlineVariant: adapter.outline_variant
    readonly property string cream: adapter.cream
    readonly property string bright: adapter.bright
    readonly property string subtle: adapter.subtle
    readonly property string dim: adapter.dim
    readonly property string faint: adapter.faint
    readonly property string iconDim: adapter.icon_dim
    readonly property string tickRest: adapter.tick_rest
    readonly property var terminal: adapter.terminal
    readonly property string paletteStyle: adapter.palette_style
    readonly property string appearanceMode: adapter.appearance_mode
    readonly property string resolvedMode: adapter.resolved_mode
    readonly property string themeSource: adapter.theme_source
    readonly property real wallpaperLuminance: adapter.wallpaper_luminance
    readonly property string recommendedLockForeground: adapter.recommended_lock_foreground

    FileView {
        id: file
        path: (Quickshell.env("XDG_CACHE_HOME") || (Quickshell.env("HOME") + "/.cache")) + "/sparrow-shell/palette.json"
        blockLoading: true
        watchChanges: true
        printErrors: false

        onFileChanged: reload()

        JsonAdapter {
            id: adapter
            property string background: "#24130f"
            property string on_background: "#ffe8df"
            property string surface: "#18120b"
            property string on_surface: "#f4ddd4"
            property string on_surface_variant: "#d8bdb3"
            property string surface_dim: "#18120b"
            property string surface_bright: "#42302b"
            property string surface_container_lowest: "#130d09"
            property string surface_container: "#251f17"
            property string surface_container_low: "#211b13"
            property string surface_container_high: "#302921"
            property string surface_container_highest: "#3b342b"
            property string primary: "#f5bd6f"
            property string on_primary: "#482900"
            property string primary_container: "#633f00"
            property string on_primary_container: "#ffddb3"
            property string primary_fixed: "#ffdcc4"
            property string primary_fixed_dim: "#ffb596"
            property string secondary: "#e9bdae"
            property string on_secondary: "#442a21"
            property string secondary_container: "#5d4035"
            property string on_secondary_container: "#ffdbcd"
            property string tertiary: "#d5c58d"
            property string on_tertiary: "#393009"
            property string tertiary_container: "#51461d"
            property string on_tertiary_container: "#f2e1a7"
            property string error: "#ffb4ab"
            property string on_error: "#690005"
            property string error_container: "#93000a"
            property string on_error_container: "#ffdad6"
            property string outline: "#9c8f80"
            property string outline_variant: "#4f4539"
            property string cream: "#e6d6cb"
            property string bright: "#fff6f0"
            property string subtle: "#b9a99e"
            property string dim: "#8a7d74"
            property string faint: "#6f635b"
            property string icon_dim: "#cdbfb4"
            property string tick_rest: "#cbb6a3"
            property var terminal: ({})
            property string palette_style: "auto"
            property string appearance_mode: "auto"
            property string resolved_mode: "dark"
            property string theme_source: "dynamic"
            property real wallpaper_luminance: 0
            property string recommended_lock_foreground: "unknown"
        }
    }
}
