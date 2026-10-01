import SwiftUI

struct Top100Screen: View {
    @State private var songs: [SongEntry] = []
    @State private var mode = "audio"
    @State private var quality = "192"
    @State private var manual = ""
    @State private var useManual = false
    @State private var isLoading = false
    @State private var log = ""
    @State private var tasks: [DownloadTask] = []
    @State private var pendingSong: SongEntry?
    @State private var busySongs = Set<String>()

    private func songKey(_ s: SongEntry) -> String { "\(s.artist) - \(s.title)" }

    var body: some View {
        NavigationView {
            Form {
                Section {
                    Toggle("크롤링 실패 시 직접 입력", isOn: $useManual)
                    if useManual {
                        TextEditor(text: $manual).frame(minHeight: 120)
                        Text("한 줄에 `가수 - 제목` 형식").font(.caption).foregroundStyle(.secondary)
                    }
                }
                Section("설정") {
                    Picker("종류", selection: $mode) {
                        Text("음원").tag("audio")
                        Text("영상").tag("video")
                    }
                    .pickerStyle(.segmented)
                    Picker("품질", selection: $quality) {
                        ForEach(mode == "audio" ? ["128", "192", "320"] : ["360p", "720p", "1080p", "best"], id: \.self) {
                            Text($0).tag($0)
                        }
                    }
                    .pickerStyle(.segmented)
                }
                Section {
                    Button {
                        load()
                    } label: {
                        HStack {
                            if isLoading { ProgressView().controlSize(.small) }
                            Text(isLoading ? "불러오는 중..." : "차트 불러오기")
                        }
                    }
                    .disabled(isLoading)
                }
                if !songs.isEmpty {
                    Section("곡 (\(songs.count))") {
                        ForEach(Array(songs.enumerated()), id: \.offset) { idx, s in
                            Top100Row(index: idx + 1, song: s) { if !busySongs.contains(songKey(s)) { pendingSong = s } }
                        }
                    }
                }
                if !tasks.isEmpty {
                    Section("진행") { ForEach(tasks) { TaskRow(task: $0, onShare: { shareFile($0) }) } }
                }
                if !log.isEmpty {
                    Section("로그") { Text(log).font(.footnote).foregroundStyle(.secondary) }
                }
            }
            .navigationTitle("멜론 TOP100")
            .alert("다운로드할까요?", isPresented: Binding(
                get: { pendingSong != nil },
                set: { if !$0 { pendingSong = nil } }
            ), presenting: pendingSong) { s in
                Button("다운로드") { pendingSong = nil; start(s) }
                Button("취소", role: .cancel) { pendingSong = nil }
            } message: { s in
                Text("\(s.artist) - \(s.title)\n\(mode == "audio" ? "음원" : "영상") \(quality)")
            }
        }
        .navigationViewStyle(.stack)
    }

    private func load() {
        isLoading = true
        log = ""
        Task { @MainActor in
            do {
                if useManual {
                    songs = try await Engine.shared.parseManual(manual)
                    log = "직접 입력 \(songs.count)곡"
                } else {
                    songs = try await Engine.shared.top100()
                    log = "차트 \(songs.count)곡"
                }
            } catch {
                log = "실패: \(error.localizedDescription). 직접 입력을 켜보세요."
            }
            isLoading = false
        }
    }

    private func start(_ s: SongEntry) {
        busySongs.insert(songKey(s))
        let task = DownloadTask(label: "\(s.artist) - \(s.title)", progress: 0, state: .running("준비 중"))
        tasks.append(task)
        Task { @MainActor in
            defer { busySongs.remove(songKey(s)) }
            do {
                let path = try await Engine.shared.searchDownload(
                    artist: s.artist, title: s.title, kind: mode, quality: quality
                )
                if let i = tasks.firstIndex(where: { $0.id == task.id }) {
                    tasks[i] = DownloadTask(label: task.label, progress: 100, state: .done(path))
                }
            } catch {
                if let i = tasks.firstIndex(where: { $0.id == task.id }) {
                    tasks[i] = DownloadTask(label: task.label, progress: 0, state: .failed(error.localizedDescription))
                }
            }
        }
    }
}
