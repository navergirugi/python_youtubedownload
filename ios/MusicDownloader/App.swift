import SwiftUI

@main
struct MusicDownloaderApp: App {
    init() {
        var lines: [String] = []
        do {
            let v = try PyBridge.ytdlpVersion()
            lines.append("PYTHON_OK yt-dlp=\(v)")
            NSLog("[MusicDownloader] Python OK, yt-dlp %@", v)
        } catch {
            lines.append("PYTHON_FAIL \(error.localizedDescription)")
            NSLog("[MusicDownloader] Python FAILED: %@", error.localizedDescription as NSString)
        }
        let path = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("engine_status.txt")
        try? lines.joined(separator: "\n").write(to: path, atomically: true, encoding: .utf8)
    }

    var body: some Scene {
        WindowGroup {
            RootView()
        }
    }
}
