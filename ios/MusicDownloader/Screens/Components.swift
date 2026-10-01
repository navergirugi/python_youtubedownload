import SwiftUI
import UIKit

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
    var onShare: ((String) -> Void)? = nil

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
                HStack {
                    Text("완료").font(.caption).foregroundStyle(.green)
                    Spacer()
                    if onShare != nil {
                        Button("공유") { onShare?(path) }
                            .font(.caption)
                    }
                }
                Text(path).font(.caption2).foregroundStyle(.secondary)
                    .lineLimit(1).truncationMode(.middle)
            case .failed(let msg):
                Text("실패: \(msg)").font(.caption).foregroundStyle(.red)
            }
        }
        .font(.subheadline)
    }
}

/// 다운로드된 파일을 iOS 공유 시트로 보낸다.
/// "파일에 저장"이면 같은 기기의 파일 앱에 저장되고,
/// AirDrop·VLC 등 같은 시트에서 다른 기기/앱 전송도 된다.
/// iPad 팝오버 크래시 방지로 sourceView를 반드시 지정한다.
func shareFile(_ path: String) {
    let url = URL(fileURLWithPath: path)
    guard let scene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
          let root = scene.windows.first?.rootViewController,
          root.presentedViewController == nil else { return }
    let vc = UIActivityViewController(activityItems: [url], applicationActivities: nil)
    if let pop = vc.popoverPresentationController {
        pop.sourceView = root.view
        pop.sourceRect = CGRect(x: root.view.bounds.midX, y: root.view.bounds.midY, width: 0, height: 0)
        pop.permittedArrowDirections = []
    }
    root.present(vc, animated: true)
}
