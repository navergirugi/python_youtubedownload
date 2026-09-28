import Foundation

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

actor Engine {
    static let shared = Engine()
    let status = "Python 엔진 미연결 (스텁)"

    func search(artist: String, title: String, kind: String) async throws -> [Candidate] {
        throw EngineError.notReady
    }

    func download(url: String, artist: String, title: String, kind: String, quality: String) async throws -> String {
        throw EngineError.notReady
    }

    func searchDownload(artist: String, title: String, kind: String, quality: String) async throws -> String {
        throw EngineError.notReady
    }

    func top100() async throws -> [SongEntry] {
        throw EngineError.notReady
    }

    func parseManual(_ text: String) throws -> [SongEntry] {
        text.split(separator: "\n").compactMap { line in
            let parts = line.split(separator: "-", maxSplits: 1).map(String.init)
            guard parts.count == 2 else { return nil }
            return SongEntry(artist: parts[0].trimmingCharacters(in: .whitespaces),
                             title: parts[1].trimmingCharacters(in: .whitespaces))
        }
    }

    func updateYtdlp() async throws {
        throw EngineError.notReady
    }
}
