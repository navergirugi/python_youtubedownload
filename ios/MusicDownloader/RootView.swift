import SwiftUI

struct RootView: View {
    @State private var tab: Tab = .audio
    @State private var sharedURL = ""

    var body: some View {
        TabView(selection: $tab) {
            Top100Screen().tabItem { Label(Tab.top100.label, systemImage: Tab.top100.symbol) }.tag(Tab.top100)
            AudioSearchScreen().tabItem { Label(Tab.audio.label, systemImage: Tab.audio.symbol) }.tag(Tab.audio)
            VideoSearchScreen().tabItem { Label(Tab.video.label, systemImage: Tab.video.symbol) }.tag(Tab.video)
            UrlScreen(sharedURL: $sharedURL).tabItem { Label(Tab.url.label, systemImage: Tab.url.symbol) }.tag(Tab.url)
            SettingsScreen().tabItem { Label(Tab.settings.label, systemImage: Tab.settings.symbol) }.tag(Tab.settings)
        }
        .onOpenURL { sharedURL = $0.absoluteString }
    }
}
