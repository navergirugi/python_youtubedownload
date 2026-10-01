import SwiftUI

struct VideoSearchScreen: View {
    @State private var artist = ""
    @State private var title = ""
    @State private var quality = "720p"
    @State private var candidates: [Candidate] = []
    @State private var tasks: [DownloadTask] = []
    @State private var isSearching = false
    @State private var log = ""
    @State private var pending: Candidate?
    @State private var busyURLs = Set<String>()

    var body: some View {
        NavigationView {
            Form {
                Section("가수명") { TextField("아이유", text: $artist) }
                Section("제목") { TextField("Celebrity", text: $title) }
                Section("화질") {
                    Picker("화질", selection: $quality) {
                        ForEach(["360p", "720p", "1080p", "best"], id: \.self) { Text($0).tag($0) }
                    }
                    .pickerStyle(.segmented)
                }
                Section {
                    Button {
                        search()
                    } label: {
                        HStack {
                            if isSearching { ProgressView().controlSize(.small) }
                            Text(isSearching ? "검색 중..." : "검색")
                        }
                    }
                    .disabled(isSearching || artist.isEmpty || title.isEmpty)
                }
                if !candidates.isEmpty {
                    Section("검색 결과") {
                        ForEach(candidates) { c in CandidateRow(candidate: c) { if !busyURLs.contains(c.url) { pending = c } } }
                    }
                }
                if !tasks.isEmpty {
                    Section("진행") {
                        ForEach(tasks) { TaskRow(task: $0, onShare: { shareFile($0) }) }
                    }
                }
                if !log.isEmpty {
                    Section("로그") { Text(log).font(.footnote).foregroundStyle(.secondary) }
                }
            }
            .navigationTitle("영상 검색")
            .alert("다운로드할까요?", isPresented: Binding(
                get: { pending != nil },
                set: { if !$0 { pending = nil } }
            ), presenting: pending) { c in
                Button("다운로드") { pending = nil; start(c) }
                Button("취소", role: .cancel) { pending = nil }
            } message: { c in
                Text("\(c.title)\n\(c.channel)")
            }
        }
        .navigationViewStyle(.stack)
    }

    private func search() {
        isSearching = true
        log = ""
        Task { @MainActor in
            do {
                let r = try await Engine.shared.search(artist: artist, title: title, kind: "video")
                candidates = r
                log = "결과 \(r.count)건"
            } catch {
                log = "실패: \(error.localizedDescription)"
            }
            isSearching = false
        }
    }

    private func start(_ c: Candidate) {
        busyURLs.insert(c.url)
        let task = DownloadTask(label: c.title, progress: 0, state: .running("준비 중"))
        tasks.append(task)
        Task { @MainActor in
            defer { busyURLs.remove(c.url) }
            do {
                let path = try await Engine.shared.download(
                    url: c.url, artist: artist, title: title, kind: "video", quality: quality
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
