import Foundation
import PythonKit

enum EngineError: LocalizedError {
    case notReady
    case python(String)

    var errorDescription: String? {
        switch self {
        case .notReady: return "다운로드 엔진이 아직 준비되지 않았습니다"
        case .python(let m): return m
        }
    }
}

struct Row: Decodable {
    let title: String
    let url: String
    let channel: String
    let duration: String
}

struct SongRow: Decodable {
    let artist: String
    let title: String
}

func decode<T: Decodable>(_ json: String) throws -> T {
    do {
        return try JSONDecoder().decode(T.self, from: Data(json.utf8))
    } catch {
        throw EngineError.python("응답 해석 실패: \(error.localizedDescription) (raw: \(String(json.prefix(200))))")
    }
}

actor Engine {
    static let shared = Engine()

    private var ready = false
    private(set) var status = "Python 엔진 준비 중"

    /// Python 초기화는 앱 시작 시 1회만 한다. yt-dlp 로드는 수 초 걸리므로 호출부에서
    /// background 로 돌리고, UI 스레드를 막지 않는다.
    static func boot() async {
        var lines: [String] = []
        do {
            let v = try await Engine.shared.run("activate_update", [])
            lines.append("PYTHON_OK yt-dlp=\(v)")
            NSLog("[MusicDownloader] Python OK, yt-dlp %@", v)
            await Engine.shared.markReady("yt-dlp \(v)")
        } catch {
            lines.append("PYTHON_FAIL \(error.localizedDescription)")
            NSLog("[MusicDownloader] Python FAILED: %@", error.localizedDescription as NSString)
            await Engine.shared.markReady("엔진 실패: \(error.localizedDescription)")
        }

        if ProcessInfo.processInfo.environment["MUSICDL_SELFTEST"] == "1" {
            lines.append(contentsOf: await Engine.shared.selfTest())
        }
        writeDiagnostics(lines)
    }

    /// 실제 네트워크를 타는 검증. 런치 인자로만 실행된다.
    private func selfTest() async -> [String] {
        var out: [String] = ["SELFTEST_BEGIN"]
        do {
            let cands = try await search(artist: "아이유", title: "Celebrity", kind: "audio")
            out.append("SEARCH_OK count=\(cands.count)")
            for c in cands.prefix(3) { out.append("  - \(c.title) | \(c.channel)") }
            if let first = cands.first {
                let path = try await download(url: first.url, artist: "아이유",
                                              title: "Celebrity", kind: "audio", quality: "192")
                out.append("DOWNLOAD_OK \(path)")
            }
        } catch {
            out.append("SELFTEST_FAIL \(error.localizedDescription)")
        }
        out.append("SELFTEST_END")
        return out
    }

    private static func writeDiagnostics(_ lines: [String]) {
        let path = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("engine_status.txt")
        try? lines.joined(separator: "\n").write(to: path, atomically: true, encoding: .utf8)
    }

    private func markReady(_ s: String) {
        status = s
        ready = true
    }

    private func ensureReady() throws {
        guard ready else { throw EngineError.notReady }
    }

    /// Python 호출은 메인 스레드에서 돌면 UI 를 막는다. 항상 background 로 보낸다.
    private func run(_ name: String, _ args: [String]) async throws -> String {
        try await Task.detached(priority: .userInitiated) {
            try PyBridge.callJSON(name, args)
        }.value
    }

    func search(artist: String, title: String, kind: String) async throws -> [Candidate] {
        try ensureReady()
        let json = try await run("_search", [artist, title, kind])
        let rows: [Row] = try decode(json)
        return rows.map {
            Candidate(title: $0.title, url: $0.url, channel: $0.channel, duration: $0.duration)
        }
    }

    func download(url: String, artist: String, title: String, kind: String, quality: String) async throws -> String {
        try ensureReady()
        // iOS에는 ffmpeg 바이너리가 없으므로: Python은 원본(m4a/mp4)만 받고,
        // MP3 변환은 정적 링크된 libav 네이티브 코드가 담당한다.
        let rawPath = try await run("download_raw", [url, artist, title, kind, quality])
        guard kind == "audio" else { return rawPath }
        let srcURL = URL(fileURLWithPath: rawPath)
        let dirURL = srcURL.deletingLastPathComponent()
        let base = srcURL.deletingPathExtension().lastPathComponent
        var dstURL = dirURL.appendingPathComponent(base).appendingPathExtension("mp3")
        var n = 1
        while FileManager.default.fileExists(atPath: dstURL.path) {
            n += 1
            dstURL = dirURL.appendingPathComponent("\(base) (\(n))").appendingPathExtension("mp3")
        }
        let bitrate = Int(quality) ?? 192
        try await Task.detached(priority: .userInitiated) {
            try Mp3Convert.convert(src: srcURL, dst: dstURL, bitrateKbps: bitrate)
        }.value
        _ = try await run("tag", [dstURL.path, artist, title])
        try? FileManager.default.removeItem(at: srcURL)
        return dstURL.path
    }

    func top100() async throws -> [SongEntry] {
        try ensureReady()
        let rows: [SongRow] = try decode(try await run("top100", []))
        return rows.map { SongEntry(artist: $0.artist, title: $0.title) }
    }

    func searchDownload(artist: String, title: String, kind: String, quality: String) async throws -> String {
        let cands = try await search(artist: artist, title: title, kind: kind)
        guard let first = cands.first else { throw EngineError.python("검색 결과가 없습니다") }
        return try await download(url: first.url, artist: artist, title: title,
                                 kind: kind, quality: quality)
    }

    func parseManual(_ text: String) throws -> [SongEntry] {
        text.split(separator: "\n").compactMap { line in
            let parts = line.split(separator: "-", maxSplits: 1).map(String.init)
            guard parts.count == 2 else { return nil }
            return SongEntry(artist: parts[0].trimmingCharacters(in: .whitespaces),
                             title: parts[1].trimmingCharacters(in: .whitespaces))
        }
    }

    struct UpdateResult: Decodable {
        let updated: Bool
        let version: String
    }

    func updateYtdlp() async throws {
        try ensureReady()
        let r: UpdateResult = try decode(try await run("update_ytdlp", []))
        await markReady("yt-dlp \(r.version)" + (r.updated ? " (갱신됨)" : " (최신)"))
    }
}
