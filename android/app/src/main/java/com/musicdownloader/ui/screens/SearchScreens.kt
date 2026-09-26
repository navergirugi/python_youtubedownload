package com.musicdownloader.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.workDataOf
import com.musicdownloader.core.Candidate
import com.musicdownloader.core.YoutubeSearch
import com.musicdownloader.util.Constants
import com.musicdownloader.util.Naming
import kotlinx.coroutines.launch

@Composable
private fun SearchScreenImpl(mode: String) {
    val scope = rememberCoroutineScope()
    val ctx = LocalContext.current
    var artist by remember { mutableStateOf("") }
    var title by remember { mutableStateOf("") }
    var cands by remember { mutableStateOf<List<Candidate>>(emptyList()) }
    var status by remember { mutableStateOf("") }
    var quality by remember { mutableStateOf(if (mode == "audio") Constants.DEFAULT_AUDIO_BITRATE else Constants.DEFAULT_VIDEO_QUALITY) }
    var confirm by remember { mutableStateOf<Candidate?>(null) }
    val qualities = if (mode == "audio") Constants.AUDIO_BITRATES else Constants.VIDEO_QUALITIES

    Column(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(artist, { artist = it }, Modifier.weight(1f), label = { Text("가수명") })
            OutlinedTextField(title, { title = it }, Modifier.weight(1f), label = { Text("제목") })
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            var expanded by remember { mutableStateOf(false) }
            Box {
                OutlinedButton(onClick = { expanded = true }) { Text(quality) }
                DropdownMenu(expanded, onDismissRequest = { expanded = false }) {
                    qualities.forEach { DropdownMenuItem(text = { Text(it) }, onClick = { quality = it; expanded = false }) }
                }
            }
            Button(onClick = {
                scope.launch {
                    status = "검색 중..."
                    try {
                        val q = if (mode == "audio") Constants.buildAudioQuery(artist, title) else Constants.buildVideoQuery(artist, title)
                        cands = YoutubeSearch.search(q)
                        status = "${cands.size}건 (행 탭 → 컨펌 후 다운로드)"
                    } catch (e: Exception) { status = "검색 실패: ${e.message}" }
                }
            }, enabled = artist.isNotBlank() || title.isNotBlank()) { Text("유튜브 검색") }
        }
        Text(status)
        LazyColumn(Modifier.weight(1f)) {
            itemsIndexed(cands) { _, c ->
                ListItem(
                    headlineContent = { Text(c.title) },
                    supportingContent = { Text("${c.channel} ${c.durationStr}\n${c.url}") },
                    trailingContent = { Button(onClick = { confirm = c }) { Text("선택") } }
                )
                HorizontalDivider()
            }
        }
    }
    confirm?.let { c ->
        val ext = if (mode == "audio") ".mp3" else ".mp4"
        val fa = artist.ifBlank { c.channel }
        val ft = title.ifBlank { c.title }
        AlertDialog(
            onDismissRequest = { confirm = null },
            title = { Text("URL 컨펌") },
            text = { Text("${c.title}\n${c.url}\n품질: $quality\n파일명: ${Naming.songFilename(fa, ft)}$ext") },
            confirmButton = {
                Button(onClick = {
                    val req = OneTimeWorkRequestBuilder<com.musicdownloader.core.DownloadWorker>()
                        .setInputData(workDataOf("watchUrl" to c.url, "artist" to fa, "title" to ft, "kind" to mode, "quality" to quality))
                        .build()
                    WorkManager.getInstance(ctx).enqueue(req)
                    confirm = null
                }) { Text("다운로드") }
            },
            dismissButton = { OutlinedButton(onClick = { confirm = null }) { Text("취소") } }
        )
    }
}

@Composable fun AudioSearchScreen() = SearchScreenImpl("audio")
@Composable fun VideoSearchScreen() = SearchScreenImpl("video")
