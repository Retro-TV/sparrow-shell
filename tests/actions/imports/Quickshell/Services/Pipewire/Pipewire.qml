pragma Singleton
import QtQml
QtObject {
    property var nodes: ({values:[]})
    property var defaultAudioSink: null
    property var defaultAudioSource: null
    property var preferredDefaultAudioSink: null
    property var preferredDefaultAudioSource: null
}
