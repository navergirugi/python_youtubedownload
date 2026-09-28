import Foundation

enum Tab: String, CaseIterable, Identifiable {
    case top100, audio, video, url, settings

    var id: String { rawValue }

    var label: String {
        switch self {
        case .top100: return "TOP100"
        case .audio: return "음원"
        case .video: return "영상"
        case .url: return "URL"
        case .settings: return "설정"
        }
    }

    var symbol: String {
        switch self {
        case .top100: return "music.note.list"
        case .audio: return "waveform"
        case .video: return "play.rectangle"
        case .url: return "link"
        case .settings: return "gearshape"
        }
    }
}
