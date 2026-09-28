import SwiftUI

struct CandidateRow: View {
    let candidate: Candidate
    let action: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(candidate.title).lineLimit(2)
            HStack(spacing: 8) {
                Text(candidate.channel).lineLimit(1)
                if !candidate.duration.isEmpty {
                    Text(candidate.duration).monospacedDigit()
                }
            }
            .font(.caption)
            .foregroundStyle(.secondary)
        }
        .contentShape(Rectangle())
        .onTapGesture(perform: action)
    }
}

struct Top100Row: View {
    let index: Int
    let song: SongEntry
    let action: () -> Void

    private var label: String {
        let n = String(index)
        let a = song.artist
        let t = song.title
        return n + ". " + a + " - " + t
    }

    var body: some View {
        Button(action: action) {
            Text(label)
                .lineLimit(1)
                .frame(maxWidth: .infinity, alignment: .leading)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}

struct TaskRow: View {
    let task: DownloadTask

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(task.label).lineLimit(1)
            switch task.state {
            case .idle:
                Text("대기")
            case .running(let note):
                HStack {
                    ProgressView()
                    Text(note).font(.caption)
                }
            case .done(let path):
                Text("완료: \(path)").font(.caption).foregroundStyle(.green)
            case .failed(let msg):
                Text("실패: \(msg)").font(.caption).foregroundStyle(.red)
            }
        }
        .font(.subheadline)
    }
}
