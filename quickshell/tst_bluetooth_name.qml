import QtQuick
import QtTest
import "sparrow/lib/bluetooth-name.js" as Names

TestCase {
    name: "BluetoothNames"
    readonly property string computedName: Names.friendlyName(bluezDevice)
    readonly property var visibleDevices: [bluezDevice].filter(Names.shouldDisplay)

    QtObject {
        id: bluezDevice
        property string address: "3B:A4:FA:7C:CB:7D"
        property string name: "3B-A4-FA-7C-CB-7D"
        property string deviceName: ""
        property bool paired: false
        property bool bonded: false
        property bool trusted: false
        property bool connected: false
    }

    Text {
        id: longName
        width: 120
        text: "An exceptionally long Bluetooth device name that must fit its row"
        elide: Text.ElideRight
    }

    function test_friendly_names() {
        compare(Names.friendlyName({name: "My Headphones", deviceName: "Headset", address: "3B:A4:FA:7C:CB:7D"}), "My Headphones");
        compare(Names.friendlyName({name: "", deviceName: "Headset", address: "3B:A4:FA:7C:CB:7D"}), "Headset");
        compare(Names.friendlyName({name: "3B-A4-FA-7C-CB-7D", deviceName: "Headset", address: "3B:A4:FA:7C:CB:7D"}), "Headset");
        compare(Names.friendlyName({name: "3B-A4-FA-7C-CB-7D", deviceName: "", address: "3B:A4:FA:7C:CB:7D"}), "Unknown device");
        compare(Names.friendlyName({name: "", deviceName: "", address: "3B:A4:FA:7C:CB:7D", paired: true, connected: true}), "Unknown device");
        compare(Names.addressLabel("3b-a4-fa-7c-cb-7d"), "3B:A4:FA:7C:CB:7D");
    }

    function test_presentation_filter() {
        var anonymous = {name: "3B-A4-FA-7C-CB-7D", deviceName: "", address: "3B:A4:FA:7C:CB:7D"};
        verify(!Names.shouldDisplay(anonymous));
        anonymous.paired = true;
        verify(Names.shouldDisplay(anonymous));
        anonymous.paired = false;
        anonymous.bonded = true;
        verify(Names.shouldDisplay(anonymous));
        anonymous.bonded = false;
        anonymous.trusted = true;
        verify(Names.shouldDisplay(anonymous));
        anonymous.trusted = false;
        anonymous.connected = true;
        verify(Names.shouldDisplay(anonymous));
        anonymous.connected = false;
        anonymous.deviceName = "Headset";
        verify(Names.shouldDisplay(anonymous));
        anonymous.name = "My Headset";
        verify(Names.shouldDisplay(anonymous));
        compare(Names.friendlyName(anonymous), "My Headset");
        verify(!Names.shouldDisplay(null));
    }

    function test_qobject_property_updates() {
        compare(Names.friendlyName(bluezDevice), "Unknown device");
        compare(computedName, "Unknown device");
        compare(visibleDevices.length, 0);
        bluezDevice.deviceName = "Advertised Headset";
        compare(Names.friendlyName(bluezDevice), "Advertised Headset");
        compare(computedName, "Advertised Headset");
        compare(visibleDevices.length, 1);
        bluezDevice.name = "My Headset";
        compare(Names.friendlyName(bluezDevice), "My Headset");
        compare(computedName, "My Headset");
        bluezDevice.deviceName = "";
        bluezDevice.name = bluezDevice.address;
        compare(visibleDevices.length, 0);
        bluezDevice.paired = true;
        compare(visibleDevices.length, 1);
        bluezDevice.paired = false;
        bluezDevice.connected = true;
        compare(visibleDevices.length, 1);
        bluezDevice.connected = false;
        compare(visibleDevices.length, 0);
        bluezDevice.name = "My renamed device";
        compare(visibleDevices.length, 1);
        compare(computedName, "My renamed device");
    }

    function test_long_name_elides() {
        verify(longName.truncated);
        verify(longName.contentWidth <= longName.width);
    }
}
