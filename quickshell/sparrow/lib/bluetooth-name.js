function isAddress(value) {
    var name = String(value || "").trim();
    return /^(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}$/.test(name);
}

function addressLabel(value) {
    var address = String(value || "").trim();
    return isAddress(address) ? address.replace(/-/g, ":").toUpperCase() : address;
}

function usefulName(device) {
    if (!device) return "";
    // BlueZ Alias (name) includes the user's chosen name; deviceName is the
    // advertised Name. Some devices advertise only their hardware address.
    var candidates = [device.name, device.deviceName];
    for (var i = 0; i < candidates.length; i++) {
        var candidate = String(candidates[i] || "").trim();
        if (candidate && !isAddress(candidate) && candidate.toUpperCase() !== addressLabel(device.address))
            return candidate;
    }
    return "";
}

function friendlyName(device) {
    return usefulName(device) || "Unknown device";
}

function shouldDisplay(device) {
    if (!device) return false;
    // BlueZ can know a device even when its current advertisement has no
    // Name. Only suppress anonymous, as-yet-unknown discovery results.
    return !!(usefulName(device) || device.paired || device.bonded
        || device.trusted || device.connected);
}
