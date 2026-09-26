package com.musicdownloader.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.workDataOf
import androidx.compose.ui.platform.LocalContext
import com.musicdownloader.core.MelonChart
import com.musicdownloader.core.SongEntry
import com.musicdownloader.core.YoutubeSearch
import com.musicdownloader.ui.rememberBatchStatus
import com.musicdownloader.util.Constants
import kotlinx.coroutines.launch

@Composable
fun Top100Screen() {
    val scope = rememberCoroutineScope()
    val ctx = LocalContext.current
    var songs by remember { mutableStateOf<List<SongEntry>>(emptyList()) }
    var status by remember { mutableStateOf("가져오기 버튼을 누르세요 (차단 시 수동 입력)") }
    var manual by remember { mutableStateOf("") }
    var bitrate by remember { mutableStateOf(Constants.DEFAULT_AUDIO_BITRATE) }
    var batchTag by remember { mutableStateOf<String?>(null) }
    val batchText = rememberBatchStatus(batchTag)

    Column(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = {
                scope.launch {
                    status = "불러오는 중..."
                    try { songs = MelonChart.fetchTop100(); status = "${songs.size}곡 로드" }
                    catch (e: Exception) { status = "차단: ${e.message} → 아래 수동 입력 사용" }
                }
            }) { Text("TOP100 가져오기") }
            var expanded by remember { mutableStateOf(false) }
            Box {
                OutlinedButton(onClick = { expanded = true }) { Text("$bitrate kbps") }
                DropdownMenu(expanded, onDismissRequest = { expanded = false }) {
                    Constants.AUDIO_BITRATES.forEach { DropdownMenuItem(text = { Text(it) }, onClick = { bitrate = it; expanded = false }) }
                }
            }
        }
        OutlinedTextField(manual, { manual = it }, Modifier.fillMaxWidth(), label = { Text("가수 - 제목 줄별 붙여넣기") }, minLines = 2)
        Button(onClick = {
            val (ok, err) = MelonChart.parseManualLines(manual)
            songs = ok; status = "수동 ${ok.size}곡 (무시 ${err.size}줄)"
        }) { Text("수동 로드") }
        Text(status)
        if (batchText.isNotBlank()) Text(batchText)
        LazyColumn(Modifier.weight(1f)) {
            itemsIndexed(songs) { i, s ->
                ListItem(
                    headlineContent = { Text("${i + 1}. ${s.artist} - ${s.title}") },
                    trailingContent = {
                        Button(onClick = {
                            scope.launch {
                                try {
                                    val found = YoutubeSearch.search(s.queryAudio(), 3).firstOrNull()
                                        ?: throw RuntimeException("검색 결과 없음")
                                    val tag = batchTag ?: "top100-${System.currentTimeMillis()}".also { batchTag = it }
                                    val req = OneTimeWorkRequestBuilder<com.musicdownloader.core.DownloadWorker>()
                                        .addTag(tag)
                                        .setInputData(workDataOf("watchUrl" to found.url, "artist" to s.artist, "title" to s.title, "kind" to "audio", "quality" to bitrate))
                                        .build()
                                    WorkManager.getInstance(ctx).enqueue(req)
                                } catch (e: Exception) {
                                    status = "실패 (${s.artist} - ${s.title}): ${e.message}"
                                }
                            }
                        }) { Text("다운") }
                    }
                )
                HorizontalDivider()
            }
        }
    }
}
