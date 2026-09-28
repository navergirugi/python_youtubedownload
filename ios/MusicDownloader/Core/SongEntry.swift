import SwiftUI

struct SongEntry: Identifiable, Hashable {
    let id = UUID()
    let artist: String
    let title: String
}
