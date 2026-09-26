package com.musicdownloader.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.workDataOf
import com.musicdownloader.core.UrlNormalize
import com.musicdownloader.core.YoutubeSearch
import com.musicdownloader.ui.rememberWorkStatus
import com.musicdownloader.util.Constants
import com.musicdownloader.util.Naming
import kotlinx.coroutines.launch
import java.util.UUID

@Composable
fun UrlScreen(initialUrl: String = "") {
    val scope = rememberCoroutineScope()
    val ctx = LocalContext.current
    var raw by remember { mutableStateOf(initialUrl) }
    var kind by remember { mutableStateOf("audio") }
    var quality by remember { mutableStateOf(Constants.DEFAULT_AUDIO_BITRATE) }
    var artist by remember { mutableStateOf("") }
    var title by remember { mutableStateOf("") }
    var status by remember { mutableStateOf("") }
    var confirmUrl by remember { mutableStateOf<String?>(null) }
    var lastId by remember { mutableStateOf<UUID?>(null) }
    val (workText, workProg) = rememberWorkStatus(lastId)

    LaunchedEffect(initialUrl) { if (initialUrl.isNotBlank()) raw = initialUrl }
    LaunchedEffect(kind) { quality = if (kind == "audio") Constants.DEFAULT_AUDIO_BITRATE else Constants.DEFAULT_VIDEO_QUALITY }

    Column(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedTextField(raw, { raw = it }, Modifier.fillMaxWidth(), label = { Text("유튜브 URL") })
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("audio" to "MP3", "video" to "MP4").forEach { (k, label) ->
                FilterChip(k == kind, { kind = k }, { Text(label) })
            }
            var expanded by remember { mutableStateOf(false) }
            val opts = if (kind == "audio") Constants.AUDIO_BITRATES else Constants.VIDEO_QUALITIES
            Box {
                OutlinedButton(onClick = { expanded = true }) { Text(quality) }
                DropdownMenu(expanded, onDismissRequest = { expanded = false }) {
                    opts.forEach { DropdownMenuItem(text = { Text(it) }, onClick = { quality = it; expanded = false }) }
                }
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(artist, { artist = it }, Modifier.weight(1f), label = { Text("가수명(자동)") })
            OutlinedTextField(title, { title = it }, Modifier.weight(1f), label = { Text("제목(자동)") })
        }
        Button(onClick = {
            val url = UrlNormalize.extractYoutubeUrl(raw)
            if (url.isEmpty()) { status = "유튜브 URL이 아닙니다"; return@Button }
            if (artist.isNotBlank() && title.isNotBlank()) { confirmUrl = url; return@Button }
            scope.launch {
                status = "정보 조회 중..."
                val (a, t, _) = YoutubeSearch.fetchUrlMeta(url)
                if (artist.isBlank()) artist = a.ifBlank { artist }
                if (title.isBlank()) title = t.ifBlank { title }
                status = "확인 후 다운로드"
                confirmUrl = url
            }
        }) { Text("URL 컨펌 후 다운로드") }
        Text(status)
        if (workText.isNotBlank()) {
            Text(workText)
            if (workProg in 1..99) LinearProgressIndicator(progress = { workProg / 100f }, modifier = Modifier.fillMaxWidth())
        }
    }
    confirmUrl?.let { url ->
        val ext = if (kind == "audio") ".mp3" else ".mp4"
        AlertDialog(
            onDismissRequest = { confirmUrl = null },
            title = { Text("URL 컨펌") },
            text = { Text("$url\n$artist - $title ($quality)\n파일명: ${Naming.songFilename(artist.ifBlank { "Unknown" }, title.ifBlank { "url_download" })}$ext") },
            confirmButton = {
                Button(onClick = {
                    val req = OneTimeWorkRequestBuilder<com.musicdownloader.core.DownloadWorker>()
                        .setInputData(workDataOf("watchUrl" to url, "artist" to artist.ifBlank { "Unknown" }, "title" to title.ifBlank { "url_download" }, "kind" to kind, "quality" to quality))
                        .build()
                    WorkManager.getInstance(ctx).enqueue(req)
                    lastId = req.id
                    confirmUrl = null; status = "다운로드 큐에 등록됨"
                }) { Text("다운로드") }
            },
            dismissButton = { OutlinedButton(onClick = { confirmUrl = null }) { Text("취소") } }
        )
    }
}
