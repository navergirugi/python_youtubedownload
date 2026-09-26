package com.musicdownloader.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun SettingsScreen() {
    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("저장 위치·정보", style = MaterialTheme.typography.titleLarge)
        Text("음원/영상: Download/MusicDownloader (MediaStore, 앱 재설치에도 유지)")
        Text("데스크탑 설정(~/.musicdownloader.json)과 별개로 동작합니다.")
        HorizontalDivider()
        Text("업데이트: GitHub Release에서 MusicDownloader-android.apk 수동 다운로드 (sideload).", style = MaterialTheme.typography.bodyMedium)
        Text("Play 스토어 배포 불가: YouTube 다운로드 TOS 위반 소지 → 사이드로드 전용.", style = MaterialTheme.typography.bodyMedium)
    }
}
