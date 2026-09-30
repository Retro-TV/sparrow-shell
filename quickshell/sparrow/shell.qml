//@ pragma UseQApplication

import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "Singletons"
import "lib/monitors.js" as Mon

/**
 * Washi pill top shell. Each monitor carries two layer-shell windows:
 *
 *  - `reserve` is a zero-content strip that only claims an exclusive zone the
 *    height of the rest pill, so tiled windows always sit below the pill even
 *    while it is expanded or a surface is open.
 *  - `overlay` is a full-screen transparent Overlay layer hosting the single
 *    morphing pill anchored at top-centre. The pill never moves windows and is
 *    never re-parented; it just grows in place, so every surface grows out of
 *    the rest pill instead of popping up as a separate panel.
 *
 * Input is routed by the window mask. While the pill is collapsed the mask is
 * the pill rect only, so the rest of the screen clicks through to windows.
 * While the pill is expanded (hovered/pinned) or a surface is open the mask is
 * cleared so the whole layer catches clicks. A backdrop press dismisses, and
 * keyboard focus is taken on demand so Escape closes the open surface.
 */
ShellRoot {
    id: root

    property string openMon: ""
    property string openSurface: ""
    property string peekMon: ""
    property var readyPillScreens: ({})
    property bool autoOnboardingOpened: false
    property real niriLayoutGaps: 8
    property real niriTopStrut: 0
    property bool niriHasLegacyOuterStruts: false

    readonly property string niriSparrowConfigPath: (Quickshell.env("XDG_CONFIG_HOME")
        || (Quickshell.env("HOME") + "/.config")) + "/niri/sparrow/"

    function refreshNiriSpacing() {
        root.niriHasLegacyOuterStruts = /^        (?:left|right|bottom) (?:[1-9][0-9]*(?:\.[0-9]+)?|0\.(?:[0-9]*[1-9][0-9]*))$/m
            .test(userAppearanceFile.text());

        var gapsMatch = userAppearanceFile.text().match(/^    gaps (-?[0-9]+(?:\.[0-9]+)?)$/m);
        if (!gapsMatch)
            gapsMatch = appearanceFile.text().match(/^    gaps (-?[0-9]+(?:\.[0-9]+)?)$/m);
        if (gapsMatch)
            root.niriLayoutGaps = Number(gapsMatch[1]);
        Flags.niriLayoutGaps = Math.max(0, root.niriLayoutGaps);

        var strutMatch = userAppearanceFile.text().match(/^        top (-?[0-9]+(?:\.[0-9]+)?)$/m);
        if (!strutMatch)
            strutMatch = appearanceFile.text().match(/^        top (-?[0-9]+(?:\.[0-9]+)?)$/m);
        if (strutMatch)
            root.niriTopStrut = Number(strutMatch[1]);
        else
            root.niriTopStrut = 0;
    }

    FileView {
        id: appearanceFile
        path: root.niriSparrowConfigPath + "appearance.kdl"
        blockLoading: true
        watchChanges: true
        printErrors: false
        onLoaded: root.refreshNiriSpacing()
        onFileChanged: reload()
    }

    FileView {
        id: userAppearanceFile
        path: root.niriSparrowConfigPath + "user-appearance.kdl"
        blockLoading: true
        watchChanges: true
        printErrors: false
        onLoaded: root.refreshNiriSpacing()
        onFileChanged: reload()
    }

    function refresh() {
    }

    // Niri output names and Qt Screen names are separate APIs. Never route a
    // known output to a different screen if the names cannot be matched.
    function focusedScreenName() {
        var outputName = Niri.focusedOutput;

        if (outputName) {
            for (var i = 0; i < Quickshell.screens.length; i++) {
                if (Quickshell.screens[i].name === outputName)
                    return Quickshell.screens[i].name;
            }
            return "";
        }

        return Quickshell.screens.length > 0 ? Quickshell.screens[0].name : "";
    }

    // ToplevelManager is backed by the foreign-toplevel protocol and reports
    // fullscreen transitions directly, including fullscreen requested by an
    // application (for example browser video). Prefer the toplevel's output
    // association so fullscreen on one monitor does not hide other pills.
    function hasFullscreenToplevelOnScreen(screenName) {
        var toplevels = ToplevelManager.toplevels.values;
        for (var i = 0; i < toplevels.length; i++) {
            var toplevel = toplevels[i];
            if (!toplevel || !toplevel.fullscreen)
                continue;

            var screens = toplevel.screens;
            for (var j = 0; j < screens.length; j++) {
                if (screens[j] && screens[j].name === screenName)
                    return true;
            }

            // Some compositors don't provide output association. In that
            // case, use the active fullscreen toplevel and Niri's focused
            // output rather than hiding every monitor.
            if (screens.length === 0 && toplevel.activated
                && ToplevelManager.activeToplevel === toplevel
                && root.focusedScreenName() === screenName)
                return true;
        }
        return false;
    }

    function screenPillBaseScale(screen) {
        if (!screen)
            return 1;
        var output = Niri.outputByName(screen.name);
        var width = output && output.logicalWidth > 0 ? output.logicalWidth : Number(screen.width);
        var height = output && output.logicalHeight > 0 ? output.logicalHeight : Number(screen.height);
        return Mon.pillBaseScale(width, height);
    }

    function outputIdentityForScreen(screen) {
        if (!screen)
            return "";
        var output = Niri.outputByName(screen.name);
        return output ? String(output.identity || output.name) : String(screen.name);
    }

    function pillEnabledOnScreen(screen) {
        return !!screen && Flags.pillVisibleOnOutput(root.outputIdentityForScreen(screen));
    }

    Component.onCompleted: {
        refresh();
        ScreenLock.initialize();
        Devices.restore();
        // Restore wallpapers independently of the lazily-created picker surface.
        Walls.startSessionRestore();
        // Probe and restore optional Night Light in the main session, not on UI open.
        NightLight.probe();
        void Niri.focusedOutput;
        sessionEnvironment.running = true;
    }

    Process {
        id: sessionEnvironment
        command: ["systemctl", "--user", "import-environment", "WAYLAND_DISPLAY", "NIRI_SOCKET"]
        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0) {
                console.error("Sparrow: could not import Wayland/Niri environment into the user service manager");
                return;
            }
            idleServiceStart.running = true;
        }
    }

    Process {
        id: idleServiceStart
        command: ["systemctl", "--user", "start", "sparrow-idle.service"]
        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0)
                console.error("Sparrow: failed to start the dedicated idle monitor service", exitCode);
        }
    }

    PanelWindow {
        id: inhibitWin
        visible: Flags.keepAwake
        implicitWidth: 1
        implicitHeight: 1
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Background
        WlrLayershell.namespace: "pill-inhibit"
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
        anchors { top: true; left: true }
        IdleInhibitor { window: inhibitWin; enabled: Flags.keepAwake }
    }

    /**
     * An empty monitor argument resolves to the focused Niri output here, so
     * keybind scripts need only their Sparrow IPC call to open a surface.
     */
    function toggleSurface(mon, surface) {
        if (!mon || mon.length === 0)
            mon = root.focusedScreenName();
        if (root.openMon === mon && root.openSurface === surface) {
            root.close();
            return;
        }
        if (root.openSurface === "getting-started" && surface !== "getting-started")
            Flags.completeOnboarding();
        root.openMon = mon;
        root.openSurface = surface;
    }

    function close() {
        if (root.openSurface === "getting-started")
            Flags.completeOnboarding();
        root.openMon = "";
        root.openSurface = "";
        root.tryAutoOpenOnboarding();
    }

    function notePillReady(screenName) {
        var ready = Object.assign({}, root.readyPillScreens);
        ready[screenName] = true;
        root.readyPillScreens = ready;
        root.tryAutoOpenOnboarding();
    }

    function tryAutoOpenOnboarding() {
        if (root.autoOnboardingOpened || !Flags.onboardingStateReady || root.openSurface.length > 0)
            return;
        var screenName = root.focusedScreenName();
        if (!screenName || !root.readyPillScreens[screenName])
            return;
        if (root.hasFullscreenToplevelOnScreen(screenName))
            return;
        if (!Flags.claimOnboardingAutoShow())
            return;
        root.autoOnboardingOpened = true;
        root.toggleSurface(screenName, "getting-started");
    }

    onOpenSurfaceChanged: root.tryAutoOpenOnboarding()

    function peek(mon) {
        root.peekMon = root.peekMon === mon ? "" : mon;
    }

    IpcHandler {
        target: "pill"
        function mixer(mon: string): void { root.toggleSurface(mon, "mixer"); }
        function calendar(mon: string): void { root.toggleSurface(mon, "calendar"); }
        function launcher(mon: string): void { root.toggleSurface(mon, "launcher"); }
        function power(mon: string): void { root.toggleSurface(mon, "power"); }
        function link(mon: string): void { root.toggleSurface(mon, "link"); }
        function battery(mon: string): void { root.toggleSurface(mon, "battery"); }
        function settings(mon: string): void { root.toggleSurface(mon, "settings"); }
        function keybinds(mon: string): void { root.toggleSurface(mon, "keybinds"); }
        function recorder(mon: string): void { root.toggleSurface(mon, "recorder"); }
        function screenrec(mon: string): void { root.toggleSurface(mon, "recorder"); }
        function record(mon: string): void { root.toggleSurface(mon, "recorder"); }

        /**
         * Quick-record IPC flow: one call cycles the whole flow with no
         * surface. Recording → stop. Counting down → cancel. A chooser already up
         * on this monitor → dismiss. Otherwise open the standalone source chooser on
         * the focused monitor `mon`, so only that pill renders it.
         */
        function quickRecord(mon: string): void {
            if (ScreenRec.recording) {
                ScreenRec.stop();
            } else if (ScreenRec.counting) {
                ScreenRec.cancel();
            } else if (ScreenRec.quickChoosing) {
                ScreenRec.quickChoosing = false;
                ScreenRec.quickScreenChoosing = false;
            } else {
                ScreenRec.quickMon = mon;
                ScreenRec.quickScreenChoosing = false;
                ScreenRec.quickChoosing = true;
            }
        }
        function sysmon(mon: string): void { root.toggleSurface(mon, "sysmon"); }
        function system(mon: string): void { root.toggleSurface(mon, "sysmon"); }
        function wallpaper(mon: string): void { root.toggleSurface(mon, "wallpaper"); }
        function nextWallpaper(): void { Walls.next(); }
        function media(mon: string): void {
            if (Players.list.length > 0)
                root.toggleSurface(mon, "media");
        }
        function peek(mon: string): void { root.peek(mon); }
        function hide(): void { root.close(); }

        /** Opens any surface by name, settings sub-pages included; dev and scripting door. */
        function page(mon: string, name: string): void { root.toggleSurface(mon, name); }

    }

    Connections {
        target: Flags
        function onOnboardingStateReadyChanged() { root.tryAutoOpenOnboarding(); }
    }

    Connections {
        target: Niri
        function onFocusedOutputChanged() { root.tryAutoOpenOnboarding(); }
    }

    Variants {
        model: Quickshell.screens

        PanelWindow {
            id: reserve
            required property var modelData
            readonly property bool monFullscreen: root.hasFullscreenToplevelOnScreen(modelData.name)
            readonly property bool pillEnabled: root.pillEnabledOnScreen(modelData)
            readonly property string outputIdentity: root.outputIdentityForScreen(modelData)
            readonly property real s: root.screenPillBaseScale(modelData) * Flags.uiScaleForOutput(outputIdentity)
            readonly property real topGap: 8 * Flags.topGapForOutput(outputIdentity) * s
            readonly property real restHeight: 38 * s
            readonly property real pillGapOffset: Math.max(-root.niriLayoutGaps,
                Flags.pillGapForOutput(outputIdentity))

            /** Keep Niri's ordinary outer gap; the Pill reserves only its body, screen spacing, and optional offset from that gap. */
            readonly property real reservedH: Math.max(0,
                restHeight + topGap + pillGapOffset - root.niriTopStrut)

            screen: modelData
            visible: pillEnabled && !monFullscreen
            color: "transparent"
            exclusionMode: ExclusionMode.Normal
            exclusiveZone: pillEnabled && !monFullscreen ? reservedH : 0
            aboveWindows: true

            anchors { top: true; left: true; right: true }
            implicitHeight: pillEnabled && !monFullscreen ? reservedH : 0

            mask: emptyReserve
            Region { id: emptyReserve }
        }
    }

    Variants {
        model: Quickshell.screens

        PanelWindow {
            id: overlay
            required property var modelData
            readonly property string outputIdentity: root.outputIdentityForScreen(modelData)
            readonly property real s: root.screenPillBaseScale(modelData) * Flags.uiScaleForOutput(outputIdentity)
            readonly property real topGap: 8 * Flags.topGapForOutput(outputIdentity) * s
            readonly property string surface: root.openMon === modelData.name ? root.openSurface : ""
            readonly property bool surfaceOpen: surface.length > 0
            readonly property bool modal: !ScreenRec.folderPickerOpen
                && (surfaceOpen || pill.held || pill.quickChoosing)

            /** A fullscreen client always owns this output; no surface or peek
             * state may summon the pill above it. */
            readonly property bool monFullscreen: root.hasFullscreenToplevelOnScreen(modelData.name)
            readonly property bool pillEnabled: root.pillEnabledOnScreen(modelData)
            readonly property bool pillHidden: monFullscreen

            // A global keybind can temporarily open a disabled output, so the
            // user can reach settings and change the display selection again.
            visible: !monFullscreen && !ScreenRec.folderPickerOpen
                && (pillEnabled || surfaceOpen)

            onMonFullscreenChanged: if (monFullscreen) {
                // Collapse without completing onboarding: a fullscreen
                // transition is not a user dismissal of that first-run page.
                if (root.openMon === modelData.name) {
                    root.openMon = "";
                    root.openSurface = "";
                }
                if (root.peekMon === modelData.name) root.peekMon = "";
                if (ScreenRec.quickMon === modelData.name) {
                    ScreenRec.quickChoosing = false;
                    ScreenRec.quickScreenChoosing = false;
                    ScreenRec.quickMon = "";
                }
                pill.pinned = false;
                pill.hovered = false;
                pill.hoverLatch = false;
            } else {
                root.tryAutoOpenOnboarding();
            }

            screen: modelData
            color: "transparent"
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: !monFullscreen && !ScreenRec.folderPickerOpen
                && (surfaceOpen || pill.quickChoosing) ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
            WlrLayershell.namespace: "pill"

            anchors { top: true; left: true; right: true; bottom: true }

            mask: monFullscreen ? hiddenRegion : (modal ? fullRegion : (pillHidden ? hiddenRegion : pillRegion))
            Region { id: hiddenRegion }
            Region {
                id: pillRegion
                readonly property real baseW: Math.max(pill.width, pill.targetW)
                x: slot.x + pill.x + (pill.width - baseW) / 2
                y: slot.y + pill.y
                width: baseW + pill.inputPadRight
                height: Math.max(pill.height, pill.targetH)
            }
            Region {
                id: fullRegion
                width: overlay.width
                height: overlay.height
            }

            MouseArea {
                anchors.fill: parent
                enabled: overlay.modal
                acceptedButtons: Qt.AllButtons
                onPressed: (mouse) => {
                    if (pill.quickChoosing) {
                        ScreenRec.quickChoosing = false;
                        ScreenRec.quickScreenChoosing = false;
                    } else if (overlay.surfaceOpen) {
                        var inside = mouse.x >= pillRegion.x && mouse.x <= pillRegion.x + pillRegion.width
                            && mouse.y >= pillRegion.y && mouse.y <= pillRegion.y + pillRegion.height;
                        if (!inside)
                            root.close();
                        else if (mouse.y <= pillRegion.y + 40 * pill.s)
                            pill.surfaceBack();
                    } else {
                        pill.pinned = false;
                        root.peekMon = "";
                    }
                }
            }

            FocusScope {
                id: focusScope
                anchors.fill: parent
                focus: overlay.surfaceOpen || pill.quickChoosing

                HoverHandler {
                    onHoveredChanged: pill.hovered = hovered
                }
                Keys.onEscapePressed: {
                    if (pill.quickChoosing) {
                        ScreenRec.quickChoosing = false;
                        ScreenRec.quickScreenChoosing = false;
                    } else if (!pill.keybindsBack()) {
                        root.close();
                    }
                }
                Keys.onUpPressed: (e) => {
                    if (pill.keybindsOpen && !pill.keybindsListening) { pill.keybindsMove(-1); e.accepted = true; return; }
                    e.accepted = pill.mixerStep(1) || pill.recorderStep(5) || pill.settingsMove(-1);
                }
                Keys.onDownPressed: (e) => {
                    if (pill.keybindsOpen && !pill.keybindsListening) { pill.keybindsMove(1); e.accepted = true; return; }
                    e.accepted = pill.mixerStep(-1) || pill.recorderStep(-5) || pill.settingsMove(1);
                }
                Keys.onLeftPressed: (e) => {
                    if (pill.mixerOpen) { pill.mixerFocusMove(-1); e.accepted = true; }
                    else if (pill.wallpaperOpen) { pill.wallpaperMove(-1); e.accepted = true; }
                    else if (pill.powerOpen) { pill.powerMove(-1); e.accepted = true; }
                    else if (pill.recorderOpen) { e.accepted = pill.recorderStep(-5); }
                    else if (pill.settingsLike) { pill.settingsAdjust(-1); e.accepted = true; }
                }
                Keys.onRightPressed: (e) => {
                    if (pill.mixerOpen) { pill.mixerFocusMove(1); e.accepted = true; }
                    else if (pill.wallpaperOpen) { pill.wallpaperMove(1); e.accepted = true; }
                    else if (pill.powerOpen) { pill.powerMove(1); e.accepted = true; }
                    else if (pill.recorderOpen) { e.accepted = pill.recorderStep(5); }
                    else if (pill.settingsLike) { pill.settingsAdjust(1); e.accepted = true; }
                }

                /**
                 * Return/Enter/Space: the wallpaper strip applies its focused
                 * thumb on every press; the power surface fires a safe tile on
                 * the first press and, for a destructive tile, holds the heat
                 * fill across autorepeat presses (drained on release). Autorepeat
                 * is swallowed for everything else so a held key never re-fires.
                 */
                Keys.onPressed: (e) => {
                    if (pill.wallpaperOpen && !pill.wallpaperSearching
                        && e.text.length === 1 && e.text > " ") {
                        pill.wallpaperType(e.text);
                        e.accepted = true;
                        return;
                    }
                    if (e.key !== Qt.Key_Return && e.key !== Qt.Key_Enter && e.key !== Qt.Key_Space)
                        return;
                    if (pill.wallpaperOpen) {
                        if (!e.isAutoRepeat) pill.wallpaperActivate();
                        e.accepted = true;
                    } else if (pill.powerOpen) {
                        if (!e.isAutoRepeat) pill.powerPress();
                        e.accepted = true;
                    } else if (pill.settingsLike) {
                        if (!e.isAutoRepeat) pill.settingsActivate();
                        e.accepted = true;
                    } else if (pill.keybindsOpen && !pill.keybindsListening) {
                        if (!e.isAutoRepeat) pill.keybindsActivate();
                        e.accepted = true;
                    }
                }
                Keys.onReleased: (e) => {
                    if (e.isAutoRepeat)
                        return;
                    if ((e.key === Qt.Key_Return || e.key === Qt.Key_Enter || e.key === Qt.Key_Space)
                        && pill.powerOpen) {
                        pill.powerRelease();
                        e.accepted = true;
                    }
                }

                /**
                 * Slot the pill rests in. While a toast is dragged the slot
                 * becomes a soft-edged mask: the pill slides against an invisible
                 * wall and dissolves at the edge it leaves through instead of
                 * getting cut. The fade lives in the padding outside the pill's
                 * resting footprint, so an unmoved pill is never touched by it.
                 */
                Item {
                    id: slot
                    readonly property real pad: 56 * overlay.s
                    readonly property bool swiping: pill.swipeX !== 0 || pill.swipeY !== 0
                    anchors.top: parent.top
                    anchors.topMargin: overlay.topGap - pad
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: pill.width + 2 * pad
                    height: pill.height + 2 * pad

                    Behavior on anchors.topMargin {
                        NumberAnimation {
                            duration: Motion.morph
                            easing.type: Motion.easeMorph
                            easing.bezierCurve: Motion.morphCurve
                        }
                    }

                    layer.enabled: swiping
                    layer.effect: MultiEffect {
                        maskEnabled: true
                        maskSource: wall
                    }

                    Item {
                        id: wall
                        width: slot.width
                        height: slot.height
                        visible: false
                        layer.enabled: true

                        Rectangle {
                            id: wallRect
                            anchors.fill: parent
                            readonly property bool sideways: pill.swipeX !== 0
                            readonly property bool leftward: pill.swipeX < 0
                            readonly property real edge: slot.pad / (sideways ? slot.width : slot.height)
                            gradient: Gradient {
                                orientation: wallRect.sideways ? Gradient.Horizontal : Gradient.Vertical
                                GradientStop { position: 0.0; color: wallRect.sideways && !wallRect.leftward ? "white" : "transparent" }
                                GradientStop { position: wallRect.edge; color: "white" }
                                GradientStop { position: 1 - wallRect.edge; color: "white" }
                                GradientStop { position: 1.0; color: wallRect.sideways && wallRect.leftward ? "white" : "transparent" }
                            }
                        }
                    }

                Pill {
                    id: pill
                    anchors.top: parent.top
                    anchors.topMargin: slot.pad
                    anchors.horizontalCenter: parent.horizontalCenter
                    s: overlay.s
                    screenName: overlay.modelData.name
                    outputIdentity: overlay.outputIdentity
                    barWindow: overlay
                    surface: overlay.surface
                    forcePinned: root.peekMon === overlay.modelData.name

                    opacity: overlay.pillHidden ? 0 : pill.swipeFade
                    Behavior on opacity {
                        enabled: !slot.swiping
                        NumberAnimation {
                            duration: Motion.morph
                            easing.type: Motion.easeMorph
                            easing.bezierCurve: Motion.morphCurve
                        }
                    }
                    transform: [
                        Translate { x: pill.swipeX; y: pill.swipeY },
                        Translate {
                            y: overlay.pillHidden ? -(pill.height + overlay.topGap) : 0
                            Behavior on y {
                                NumberAnimation {
                                    duration: Motion.morph
                                    easing.type: Motion.easeMorph
                                    easing.bezierCurve: Motion.morphCurve
                                }
                            }
                        }
                    ]

                    onRequestSurface: (name) => root.toggleSurface(overlay.modelData.name, name)
                    onRequestClose: root.close()
                    onOnboardingReady: (screenName) => root.notePillReady(screenName)
                }
                }
            }

            onSurfaceOpenChanged: if (surfaceOpen) focusScope.forceActiveFocus()

            Connections {
                target: pill
                function onQuickChoosingChanged() {
                    if (pill.quickChoosing)
                        focusScope.forceActiveFocus();
                }
                function onWallpaperSearchingChanged() {
                    if (!pill.wallpaperSearching && overlay.surfaceOpen)
                        focusScope.forceActiveFocus();
                }
                function onKeybindsListeningChanged() {
                    if (!pill.keybindsListening && overlay.surfaceOpen)
                        focusScope.forceActiveFocus();
                }
            }
        }
    }
}
