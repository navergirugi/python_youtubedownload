import Foundation

struct Candidate: Identifiable, Hashable {
    let id = UUID()
    let title: String
    let url: String
    let channel: String
    let duration: String
}

enum DownloadState: Equatable {
    case idle
    case running(String)
    case done(String)
    case failed(String)
}

struct DownloadTask: Identifiable, Equatable {
    let id = UUID()
    let label: String
    var progress: Int
    var state: DownloadState

    static func == (a: DownloadTask, b: DownloadTask) -> Bool { a.id == b.id }
}
