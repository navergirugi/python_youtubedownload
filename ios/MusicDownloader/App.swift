import SwiftUI

@main
struct MusicDownloaderApp: App {
    init() {
        Task { await Engine.boot() }
    }

    var body: some Scene {
        WindowGroup {
            RootView()
        }
    }
}
