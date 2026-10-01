import SwiftUI

struct SettingsScreen: View {
    @AppStorage("audioDir") private var audioDir = ""
    @AppStorage("videoDir") private var videoDir = ""
    @AppStorage("ytdlpAutoUpdate") private var ytdlpAutoUpdate = true
    @State private var engineInfo = ""

    var body: some View {
        NavigationView {
            Form {
                Section("저장 위치") {
                    HStack {
                        Text("음원")
                        Spacer()
                        Text(audioDir.isEmpty ? "기본" : audioDir)
                            .foregroundColor(.secondary)
                    }
                    HStack {
                        Text("영상")
                        Spacer()
                        Text(videoDir.isEmpty ? "기본" : videoDir)
                            .foregroundColor(.secondary)
                    }
                }
                Section("yt-dlp") {
                    Toggle("자동 업데이트", isOn: $ytdlpAutoUpdate)
                    Text("유튜브가 방어를 자주 바꾸므로 최신 버전이어야 정상 동작합니다.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Button("지금 업데이트") {
                        Task {
                            engineInfo = "업데이트 중..."
                            do {
                                try await Engine.shared.updateYtdlp()
                                engineInfo = "완료"
                            } catch {
                                engineInfo = "실패: \(error.localizedDescription)"
                            }
                        }
                    }
                }
                Section("엔진") {
                    Text(engineInfo.isEmpty ? Engine.shared.status : engineInfo)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("설정")
        }
    }
}
