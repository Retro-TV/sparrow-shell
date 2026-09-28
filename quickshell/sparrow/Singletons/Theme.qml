pragma Singleton
import QtQuick
import Quickshell

/**
 * Stable design tokens mapped from the current canonical semantic palette.
 * Static and dynamic source selection happens upstream; this singleton never
 * recolors or adjusts Matugen roles on its own.
 */
Singleton {
    readonly property color onGlow: Dyn.primary
    readonly property color verm: Dyn.primaryContainer
    readonly property color vermLit: Dyn.primary
    readonly property color vermDeep: Dyn.primaryContainer
    readonly property color cream: Dyn.cream
    readonly property color bright: Dyn.bright
    readonly property color dim: Dyn.dim
    readonly property color cardTop: Dyn.surfaceContainerHigh
    readonly property color cardBot: Dyn.surfaceContainerLow
    readonly property color border: Dyn.outlineVariant
    readonly property color shadow:     Qt.rgba(0, 0, 0, 0.55)
    readonly property color tileBg: Dyn.surface
    readonly property color subtle: Dyn.subtle
    readonly property color faint: Dyn.faint
    readonly property color iconDim: Dyn.iconDim
    readonly property color hair:     Qt.alpha(cream, 0.13)
    readonly property color hairSoft: Qt.alpha(cream, 0.08)
    readonly property color sheen:    Qt.alpha(cream, 0.07)
    readonly property color vermDim: Dyn.secondaryContainer
    readonly property color vermDimDeep: Dyn.surfaceContainerLowest
    readonly property color vermBurn: Dyn.primaryContainer
    readonly property color tickRest: Dyn.tickRest
    readonly property color threadBg:  Qt.alpha(cream, 0.13)
    readonly property color flameCore: Dyn.onPrimary
    readonly property color flameGlow: onGlow

    /**
     * Flame canvas ramp: literal hex strings (color type won't work), fed
     * directly to Canvas addColorStop/strokeStyle. A color property serializes
     * to #aarrggbb and corrupts the gradient render, so the dynamic branch passes
     * matugen's raw hex strings through untouched rather than any Qt.darker math.
     */
    readonly property string flameInk: Dyn.primary
    readonly property string flameEmber: Dyn.primaryContainer
    readonly property string flameBurn: Dyn.primaryContainer
    readonly property string flameTip: Dyn.onPrimaryContainer
    readonly property color todayWarm: onGlow
    readonly property color ghost: Dyn.surfaceContainerHighest
    readonly property color frameBg:      Qt.alpha(cream, 0.055)
    readonly property color frameBorder:  Qt.alpha(cream, 0.10)
    readonly property color creamMenu:     Qt.alpha(cream, 0.82)
    readonly property real shadowOpacity: 0.5
    /** Snapshot of installed system families for the font picker and font validation. */
    property var fontFamilies: Qt.fontFamilies()
    // Inter Black is the product default used by Sparrow's canonical desktop.
    // Keep a saved font choice when installed; an empty/missing preference on a
    // fresh account (or after Reset in Look) resolves to the same default.
    readonly property string font: (Flags.uiFont.length > 0 && fontFamilies.indexOf(Flags.uiFont) >= 0) ? Flags.uiFont : "Inter Black"

    /**
     * MPRIS trackArtists arrives as a JS array from some players and as a
     * plain string from others (Spotify); calling join on the string throws
     * and kills the whole binding. Handles both, falls back to trackArtist.
     */
    function joinArtists(artists, single) {
        if (artists && typeof artists.join === "function" && artists.length > 0)
            return artists.join(", ");
        if (artists && String(artists).length > 0)
            return String(artists);
        return single ? String(single) : "";
    }
}
