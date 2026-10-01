import SwiftUI

struct UrlScreen: View {
    @Binding var sharedURL: String
    @State private var url = ""
    @State private var artist = ""
    @State private var title = ""
    @State private var kind = "audio"
    @State private var quality = "192"
    @State private var task: DownloadTask?
    @State private var log = ""

    var body: some View {
        NavigationView {
            Form {
                Section("URL") {
                    TextField("https://youtube.com/watch?v=...", text: $url)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                }
                Section("종류") {
                    Picker("종류", selection: $kind) {
                        Text("음원").tag("audio")
                        Text("영상").tag("video")
                    }
                    .pickerStyle(.segmented)
                    Picker("품질", selection: $quality) {
                        ForEach(kind == "audio" ? ["128", "192", "320"] : ["360p", "720p", "1080p", "best"], id: \.self) {
                            Text($0).tag($0)
                        }
                    }
                    .pickerStyle(.segmented)
                }
                Section("파일명") {
                    TextField("가수명", text: $artist)
                    TextField("제목", text: $title)
                }
                Section {
                    Button("다운로드") {
                        start()
                    }
                    .disabled(url.isEmpty)
                }
                if let t = task {
                    Section("진행") { TaskRow(task: t) }
                }
                if !log.isEmpty {
                    Section("로그") { Text(log).font(.footnote).foregroundStyle(.secondary) }
                }
            }
            .navigationTitle("URL 직접")
            .onAppear {
                if !sharedURL.isEmpty {
                    url = sharedURL
                    sharedURL = ""
                }
            }
        }
    }

    private func start() {
        let t = DownloadTask(label: artist.isEmpty ? url : "\(artist) - \(title)", progress: 0, state: .running("준비 중"))
        task = t
        log = ""
        Task {
            do {
                let path = try await Engine.shared.download(
                    url: url, artist: artist, title: title, kind: kind, quality: quality
                )
                task = DownloadTask(label: t.label, progress: 100, state: .done(path))
            } catch {
                task = DownloadTask(label: t.label, progress: 0, state: .failed(error.localizedDescription))
                log = error.localizedDescription
            }
        }
    }
}
