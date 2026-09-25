pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Services.Notifications

Singleton {
    id: root

    property var seenIds: ({})
    property var arrivalMs: ({})
    property var popups: []
    property int tick: 0
    property var expandedApps: ({})
    property var history: []
    property var userDismissed: ({})
    property var expireAt: ({})
    property var hookedIds: ({})

    readonly property double nextExpiry: {
        var next = 0;
        var deadlines = expireAt;
        for (var id in deadlines) {
            var deadline = deadlines[id];
            if (deadline > 0 && (!next || deadline < next))
                next = deadline;
        }
        return next;
    }

    readonly property var tracked: server.trackedNotifications.values
    readonly property int count: tracked.length + history.length

    readonly property int unread: {
        var u = 0;
        for (var i = 0; i < tracked.length; i++)
            if (!seenIds[tracked[i].id]) u++;
        return u;
    }

    readonly property var groups: {
        var map = {};
        var order = [];
        for (var i = 0; i < tracked.length; i++) {
            var n = tracked[i];
            var app = (n.appName && n.appName.length) ? n.appName : "System";
            if (map[app] === undefined) { map[app] = []; order.push(app); }
            map[app].push({ live: true, n: n, t: arrivalMs[n.id] || 0 });
        }
        for (var j = 0; j < history.length; j++) {
            var h = history[j];
            if (map[h.app] === undefined) { map[h.app] = []; order.push(h.app); }
            map[h.app].push({ live: false, n: h, t: h.ts || 0 });
        }
        function coalesce(list, it) {
            var last = list.length > 0 ? list[list.length - 1] : null;
            if (last && last.n.summary === it.n.summary && last.n.body === it.n.body) {
                last.count++;
                last.items.push(it.n);
            } else {
                list.push({ live: it.live, n: it.n, count: 1, items: [it.n] });
            }
        }
        var gs = order.map(function(app) {
            var items = map[app];
            items.sort(function(a, b) { return b.t - a.t; });
            var criticals = [];
            var entries = [];
            for (var k = 0; k < items.length; k++)
                coalesce(items[k].n.urgency === NotificationUrgency.Critical ? criticals : entries, items[k]);
            var preview = items.find(function(it) { return it.n.urgency !== NotificationUrgency.Critical; });
            return {
                app: app,
                count: items.length,
                t: items[0].t,
                newest: items[0].n,
                preview: preview ? preview.n : items[0].n,
                criticals: criticals,
                entries: entries
            };
        });
        gs.sort(function(a, b) { return b.t - a.t; });
        return gs;
    }

    function iconFor(n) {
        if (!n) return "";
        var img = n.image || "";
        var names = [];
        if (img.indexOf("image://icon/") === 0) {
            names.push(img.substring(13));
        } else if (img.length && !/\.svg$/i.test(img)) {
            return img;
        }
        names.push(n.appIcon, n.desktopEntry, (n.appName || n.app || "").toLowerCase());
        for (var i = 0; i < names.length; i++) {
            var nm = names[i];
            if (!nm || !nm.length) continue;
            if (nm.indexOf("/") === 0 || nm.indexOf("file://") === 0) return nm;
            var p = Quickshell.iconPath(nm, true);
            if (p.length) return p;
        }
        return "";
    }

    function dismissEntry(e) {
        if (!e || !e.items) return;
        var d = Object.assign({}, userDismissed);
        var gone = {};
        var live = [];
        for (var i = 0; i < e.items.length; i++) {
            var n = e.items[i];
            if (typeof n.dismiss === "function") {
                d[n.id] = true;
                live.push(n);
            } else {
                gone[n.id] = true;
            }
        }
        root.userDismissed = d;
        for (var j = 0; j < live.length; j++) live[j].dismiss();
        root.history = root.history.filter(function(h) { return !gone[h.id]; });
    }

    /** Focus an exact app-id match through Sparrow's centralized Niri backend. */
    function raiseWindow(n) {
        if (!n)
            return false;
        return Niri.focusApplicationWindow(n.desktopEntry, n.appName);
    }

    /**
     * Open the app behind a notification: invoke its default action when present,
     * then jump to the app's window, mirroring stock notification-center behavior.
     */
    function activateNotif(n) {
        if (!n) return;
        var acts = n.actions || [];
        for (var i = 0; i < acts.length; i++) {
            if (acts[i].identifier === "default") {
                acts[i].invoke();
                break;
            }
        }
        raiseWindow(n);
    }

    /** Inbox-row entry wrapper: activate the app, then dismiss the entry. */
    function activateEntry(e) {
        if (!e || !e.n) return;
        activateNotif(e.n);
        dismissEntry(e);
    }

    function dismissApp(app) {
        var doomed = tracked.filter(function(n) {
            return ((n.appName && n.appName.length) ? n.appName : "System") === app;
        });
        var d = Object.assign({}, userDismissed);
        for (var i = 0; i < doomed.length; i++) d[doomed[i].id] = true;
        root.userDismissed = d;
        for (var j = 0; j < doomed.length; j++) doomed[j].dismiss();
        root.history = root.history.filter(function(h) { return h.app !== app; });
    }

    function markAllSeen() {
        var m = {};
        for (var i = 0; i < tracked.length; i++) m[tracked[i].id] = true;
        root.seenIds = m;
    }

    function clearAll() {
        var l = tracked.slice();
        var d = Object.assign({}, userDismissed);
        for (var i = 0; i < l.length; i++) d[l[i].id] = true;
        root.userDismissed = d;
        for (var j = 0; j < l.length; j++) l[j].dismiss();
        root.history = [];
        root.popups = [];
    }

    function removePopup(n) {
        if (!n) return;
        root.popups = root.popups.filter(function(p) { return p !== n; });
    }

    /**
     * The Quickshell 0.3.1 property is documented in seconds, but that release
     * stores the raw D-Bus expire_timeout value without converting it. Keep
     * the protocol's millisecond unit here. Honor explicit timeouts, treat 0
     * as persistent, and retain Sparrow's urgency defaults for -1.
     */
    function notificationDeadline(n, now) {
        var timeout = Number(n.expireTimeout);
        if (timeout > 0)
            return now + timeout;
        if (timeout === 0)
            return 0;
        if (n.urgency === NotificationUrgency.Critical)
            return 0;
        return now + (n.urgency === NotificationUrgency.Low ? 4000 : 6000);
    }

    function updateLifetime(n, resetArrival) {
        if (!n) return;
        var now = Date.now();
        if (resetArrival) {
            var a = Object.assign({}, root.arrivalMs);
            a[n.id] = now;
            root.arrivalMs = a;
        }
        var e = Object.assign({}, root.expireAt);
        var deadline = notificationDeadline(n, now);
        if (deadline > 0)
            e[n.id] = deadline;
        else
            delete e[n.id];
        root.expireAt = e;
    }

    function expireDue() {
        var now = Date.now();
        var due = tracked.filter(function(n) {
            var deadline = root.expireAt[n.id];
            return deadline > 0 && deadline <= now;
        });
        for (var i = 0; i < due.length; i++)
            due[i].expire();
    }

    function refreshReplaced(n) {
        if (!n) return;
        root.updateLifetime(n, true);
        var critical = n.urgency === NotificationUrgency.Critical;
        if (!Flags.dnd || critical) {
            var updated = root.popups.filter(function(p) { return p.id !== n.id; });
            root.popups = updated.concat([n]).slice(-3);
        }
    }

    function toggleExpanded(app) {
        var e = Object.assign({}, expandedApps);
        e[app] = e[app] !== true;
        root.expandedApps = e;
    }

    /**
     * Bind the history-snapshot handler to a notification's `closed` signal once.
     * `keepOnReload` re-runs Component.onCompleted on every QS reload over the
     * still-tracked notifications, so the id set gates re-hooks: without it each
     * reload would stack another handler and a single close would push duplicate
     * history rows. The id is cleared inside the handler so a later notification
     * reusing the id re-hooks cleanly.
     */
    function hookClosed(n) {
        if (root.hookedIds[n.id])
            return;
        var hooked = Object.assign({}, root.hookedIds);
        hooked[n.id] = true;
        root.hookedIds = hooked;
        n.closed.connect(function(reason) {
            if (!root.userDismissed[n.id])
                root.history = [{
                    app: (n.appName && n.appName.length) ? n.appName : "System",
                    summary: n.summary,
                    body: n.body,
                    appIcon: n.appIcon,
                    desktopEntry: n.desktopEntry,
                    image: n.image,
                    urgency: n.urgency,
                    ts: root.arrivalMs[n.id] || Date.now(),
                    id: "h" + n.id + "-" + Date.now()
                }].concat(root.history).slice(0, 50);
            else {
                var du = Object.assign({}, root.userDismissed);
                delete du[n.id];
                root.userDismissed = du;
            }
            root.removePopup(n);
            var b = Object.assign({}, root.arrivalMs);
            delete b[n.id];
            root.arrivalMs = b;
            var c = Object.assign({}, root.expireAt);
            delete c[n.id];
            root.expireAt = c;
            var h = Object.assign({}, root.hookedIds);
            delete h[n.id];
            root.hookedIds = h;
        });

        var refresh = function() { root.refreshReplaced(n); };
        n.expireTimeoutChanged.connect(refresh);
        n.appNameChanged.connect(refresh);
        n.appIconChanged.connect(refresh);
        n.summaryChanged.connect(refresh);
        n.bodyChanged.connect(refresh);
        n.urgencyChanged.connect(refresh);
        n.actionsChanged.connect(refresh);
        n.imageChanged.connect(refresh);
        n.hintsChanged.connect(refresh);
    }

    function ageLabel(n) {
        void root.tick;
        var t = arrivalMs[n.id] || n.ts;
        if (!t) return "";
        var m = Math.floor((Date.now() - t) / 60000);
        if (m < 1) return "now";
        if (m < 60) return m + "m";
        return Math.floor(m / 60) + "h";
    }

    Timer {
        interval: 30000
        running: root.count > 0
        repeat: true
        onTriggered: root.tick++
    }

    Timer {
        interval: Math.max(1, root.nextExpiry - Date.now())
        running: root.nextExpiry > 0
        repeat: false
        onTriggered: {
            root.expireDue();
            if (root.nextExpiry > 0)
                restart();
        }
    }

    NotificationServer {
        id: server
        keepOnReload: true
        bodySupported: true
        actionsSupported: true
        imageSupported: true

        Component.onCompleted: {
            var l = trackedNotifications.values;
            var a = Object.assign({}, root.arrivalMs);
            for (var i = 0; i < l.length; i++) {
                if (!a[l[i].id]) a[l[i].id] = Date.now();
                root.hookClosed(l[i]);
                if (root.expireAt[l[i].id] === undefined)
                    root.updateLifetime(l[i], false);
            }
            root.arrivalMs = a;
        }

        onNotification: function(n) {
            root.updateLifetime(n, true);
            n.tracked = true;
            root.hookClosed(n);
            var critical = n.urgency === NotificationUrgency.Critical;
            if (!Flags.dnd || critical)
                root.popups = root.popups.concat([n]).slice(-3);
        }
    }
}
