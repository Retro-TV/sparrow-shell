pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

/**
 * Shared session flags persisted to a small JSON file and watched for external
 * change, so every Sparrow daemon (pill, idle) reads and writes the same
 * Do-Not-Disturb and Keep-Awake state live without a second notification server
 * or idle inhibitor. Toggling in one surface updates the others on the next file
 * event, and the state survives a daemon restart.
 */
Singleton {
    id: root

    property bool flagsStateReady: false
    property bool flagsFileExisted: false
    property bool onboardingFileMissing: false
    property bool onboardingStateReady: false
    /** Temporary hand-off used when Display opens the Pill settings for one output. */
    property string pillSettingsOutputIdentity: ""
    /** Current Niri layout gap, exposed to Pill controls for a safe negative offset limit. */
    property real niriLayoutGaps: 8

    readonly property bool onboardingCompleted: onboardingAdapter.completed
    readonly property bool onboardingAutoPending: onboardingStateReady
        && !onboardingAdapter.completed && !onboardingAdapter.autoShown

    function initializeOnboardingState() {
        if (!flagsStateReady || !onboardingFileMissing || onboardingStateReady)
            return;

        // A pre-onboarding Sparrow flags file (or migrated legacy state) means
        // this is an upgrade, not a new user. Keep flags.json untouched.
        onboardingAdapter.completed = flagsFileExisted;
        onboardingAdapter.autoShown = flagsFileExisted;
        onboardingStateReady = true;
        onboardingFile.writeAdapter();
    }

    function claimOnboardingAutoShow() {
        if (!onboardingAutoPending)
            return false;
        onboardingAdapter.autoShown = true;
        onboardingFile.writeAdapter();
        return true;
    }

    function completeOnboarding() {
        if (!onboardingStateReady)
            return;
        onboardingAdapter.completed = true;
        onboardingAdapter.autoShown = true;
        onboardingFile.writeAdapter();
    }

    property alias dnd: adapter.dnd
    property alias keepAwake: adapter.keepAwake
    property alias time12h: adapter.time12h
    property alias clockSeconds: adapter.clockSeconds
    property alias paletteMode: adapter.paletteMode
    property alias paletteVariant: adapter.paletteVariant
    property alias appearanceMode: adapter.appearanceMode
    property alias lockForegroundMode: adapter.lockForegroundMode
    property alias wallpaperDir: adapter.wallpaperDir
    property alias wallhavenGeneral: adapter.wallhavenGeneral
    property alias wallhavenAnime: adapter.wallhavenAnime
    property alias wallhavenPeople: adapter.wallhavenPeople
    property alias wallhavenSfw: adapter.wallhavenSfw
    property alias wallhavenSketchy: adapter.wallhavenSketchy
    property alias wallhavenNsfw: adapter.wallhavenNsfw
    property alias wallhavenSorting: adapter.wallhavenSorting
    property alias wallhavenTopRange: adapter.wallhavenTopRange
    property alias randomScope: adapter.randomScope
    property alias uiScale: adapter.uiScale
    property alias pillByOutput: adapter.pillByOutput
    property alias pillDisplayMode: adapter.pillDisplayMode
    property alias reduceMotion: adapter.reduceMotion
    property alias uiFont: adapter.uiFont
    property alias pillGap: adapter.pillGap
    property alias topGap: adapter.topGap
    property alias appGap: adapter.appGap
    property alias recordCountdown: adapter.recordCountdown
    property alias recordDir: adapter.recordDir
    property alias recordFps: adapter.recordFps
    property alias recordQuality: adapter.recordQuality
    property alias recordCursor: adapter.recordCursor
    property alias recordMic: adapter.recordMic
    property alias recordDesktop: adapter.recordDesktop
    property alias recordClearedBefore: adapter.recordClearedBefore
    property alias idleLockMin: adapter.idleLockMin
    property alias idleScreenOffMin: adapter.idleScreenOffMin
    property alias idleSuspendMin: adapter.idleSuspendMin
    property alias weatherCity: adapter.weatherCity
    property alias musicViz: adapter.musicViz
    property alias nightLightMode: adapter.nightLightMode
    property alias nightLightTemp: adapter.nightLightTemp
    property alias nightLightOnMin: adapter.nightLightOnMin
    property alias nightLightOffMin: adapter.nightLightOffMin

    FileView {
        id: file
        path: (Quickshell.env("XDG_STATE_HOME") || (Quickshell.env("HOME") + "/.local/state")) + "/sparrow-shell/flags.json"
        blockLoading: true
        watchChanges: true
        printErrors: false

        onFileChanged: reload()
        onLoaded: {
            root.flagsStateReady = true;
            root.flagsFileExisted = true;
            root.initializeOnboardingState();
        }
        onAdapterUpdated: writeAdapter()
        onLoadFailed: function(error) {
            if (error === FileViewError.FileNotFound) {
                root.flagsStateReady = true;
                root.flagsFileExisted = false;
                root.initializeOnboardingState();
                writeAdapter();
            }
        }

        JsonAdapter {
            id: adapter
            property bool dnd: false
            property bool keepAwake: false
            property bool time12h: false
            property bool clockSeconds: false
            property string paletteMode: "dynamic"
            /** Matugen scheme selection: auto, tonal, content, or monochrome. */
            property string paletteVariant: "auto"
            /** Dynamic mode only; auto delegates light/dark selection to Matugen. */
            property string appearanceMode: "auto"
            property int paletteSettingsVersion: 1
            property string lockForegroundMode: "auto"
            /** Explicit wallpaper folder override. Empty means autodetect: wallpaper.sh's last resolved directory in sparrow-shell/wallpaper-dir, then $HOME/Pictures/wallpapers. Lives in user state, independently of the portable shell configuration. */
            property string wallpaperDir: ""
            /** Wallhaven search filters are local user preferences, separate from the secret API key. */
            property bool wallhavenGeneral: true
            property bool wallhavenAnime: true
            property bool wallhavenPeople: false
            property bool wallhavenSfw: true
            property bool wallhavenSketchy: true
            property bool wallhavenNsfw: true
            property string wallhavenSorting: "toplist"
            property string wallhavenTopRange: "1M"
            /** Super+B random target: "all" repaints every monitor, "cursor" only the one under the pointer. */
            property string randomScope: "all"
            property real uiScale: 1.0
            /** "all" shows a Pill on every screen; "selected" uses each output's enabled flag. */
            property string pillDisplayMode: "all"
            /** Optional per-output visibility, UI scale, and Pill gap overrides, keyed by Niri output identity. */
            property var pillByOutput: ({})
            property bool reduceMotion: false
            property string uiFont: ""
            /** Offset from Niri's normal layout gap between Pill and tiled windows. */
            property real pillGap: 0.0
            /** Screen-edge gap as a fraction of the 8px scaled spacing unit. 0 sits the pill flush to the screen edge. */
            property real topGap: 1.1
            // Legacy Pill-to-window spacing retained for migration of old
            // user-appearance.kdl files; new spacing uses Look's Niri Gap.
            property real appGap: 1.0
            property int recordCountdown: 5
            property string recordDir: ""
            property int recordFps: 60
            property string recordQuality: "high"
            property bool recordCursor: true
            property bool recordMic: true
            property bool recordDesktop: true
            property real recordClearedBefore: 0
            property int idleLockMin: 5
            property int idleScreenOffMin: 6
            property int idleSuspendMin: 0
            property string weatherCity: ""
            property bool musicViz: true
            property string nightLightMode: "off"
            property int nightLightTemp: 4000
            property int nightLightOnMin: 1260
            property int nightLightOffMin: 450
        }
    }

    function pillOutputValue(identity, key, fallback) {
        var overrides = pillByOutput || {};
        var output = overrides[String(identity || "")] || {};
        return Object.prototype.hasOwnProperty.call(output, key) ? output[key] : fallback;
    }

    function pillVisibleOnOutput(identity) {
        return pillDisplayMode !== "selected"
            || pillOutputValue(identity, "enabled", false) === true;
    }

    function setPillOutputEnabled(identity, enabled) {
        setPillOutputValue(identity, "enabled", enabled === true);
    }

    function setPillOutputValue(identity, key, value) {
        var id = String(identity || "");
        if (!id)
            return;
        var next = Object.assign({}, pillByOutput || {});
        var output = Object.assign({}, next[id] || {});
        if (value === null || value === undefined)
            delete output[key];
        else
            output[key] = value;
        if (Object.keys(output).length > 0)
            next[id] = output;
        else
            delete next[id];
        pillByOutput = next;
    }

    function uiScaleForOutput(identity) {
        return Number(pillOutputValue(identity, "uiScale", uiScale));
    }

    function topGapForOutput(identity) {
        return Number(pillOutputValue(identity, "topGap", topGap));
    }

    function pillGapForOutput(identity) {
        return Number(pillOutputValue(identity, "pillGap", pillGap));
    }

    FileView {
        id: onboardingFile
        path: (Quickshell.env("XDG_STATE_HOME") || (Quickshell.env("HOME") + "/.local/state")) + "/sparrow-shell/onboarding.json"
        blockLoading: true
        watchChanges: true
        printErrors: false

        onFileChanged: reload()
        onLoaded: root.onboardingStateReady = true
        onAdapterUpdated: writeAdapter()
        onLoadFailed: function(error) {
            if (error === FileViewError.FileNotFound) {
                root.onboardingFileMissing = true;
                root.initializeOnboardingState();
            }
        }

        JsonAdapter {
            id: onboardingAdapter
            property bool completed: false
            property bool autoShown: false
        }
    }
}
