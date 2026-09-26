package com.musicdownloader.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.Observer
import androidx.work.WorkInfo
import androidx.work.WorkManager
import java.util.UUID

// WorkManager 상태를 화면에 보여주기 위한 옵저버 (추가 의존성 없음).
@Composable
fun rememberWorkStatus(id: UUID?): Pair<String, Int> {
    val ctx = LocalContext.current
    var text by remember { mutableStateOf("") }
    var prog by remember { mutableIntStateOf(0) }
    LaunchedEffect(id) {
        text = if (id == null) "" else "대기 중..."
        prog = 0
    }
    DisposableEffect(id) {
        val owner = ctx as? LifecycleOwner
        if (id == null || owner == null) return@DisposableEffect onDispose {}
        val live = WorkManager.getInstance(ctx).getWorkInfoByIdLiveData(id)
        val obs = Observer<WorkInfo?> { info ->
            when (info?.state) {
                WorkInfo.State.ENQUEUED -> { text = "대기 중..."; prog = 0 }
                WorkInfo.State.RUNNING -> {
                    val p = info.progress.getInt("progress", 0)
                    prog = p
                    text = "다운로드 중... $p%"
                }
                WorkInfo.State.SUCCEEDED -> {
                    prog = 100
                    text = "완료: " + (info.outputData.getString("displayPath") ?: info.outputData.getString("path") ?: "")
                }
                WorkInfo.State.FAILED -> {
                    text = "실패: " + (info.outputData.getString("error") ?: "알 수 없음")
                }
                WorkInfo.State.CANCELLED -> text = "취소됨"
                WorkInfo.State.BLOCKED -> text = "대기 중..."
                null -> {}
            }
        }
        live.observe(owner, obs)
        onDispose { live.removeObserver(obs) }
    }
    return text to prog
}

// TOP100 일괄 다운로드 요약 (같은 태그로 묶은 작업들을 집계).
@Composable
fun rememberBatchStatus(tag: String?): String {
    val ctx = LocalContext.current
    var text by remember { mutableStateOf("") }
    LaunchedEffect(tag) { text = "" }
    DisposableEffect(tag) {
        val owner = ctx as? LifecycleOwner
        if (tag == null || owner == null) return@DisposableEffect onDispose {}
        val live = WorkManager.getInstance(ctx).getWorkInfosByTagLiveData(tag)
        val obs = Observer<List<WorkInfo>> { list ->
            val done = list.count { it.state == WorkInfo.State.SUCCEEDED }
            val failed = list.count { it.state == WorkInfo.State.FAILED || it.state == WorkInfo.State.CANCELLED }
            val running = list.count { it.state == WorkInfo.State.RUNNING }
            val firstErr = list.firstOrNull { it.state == WorkInfo.State.FAILED }
                ?.outputData?.getString("error")
            text = buildString {
                append("성공 $done / 실패 $failed / 전체 ${list.size}")
                if (running > 0) append(" (진행 중 $running)")
                if (failed > 0 && firstErr != null) append("\n최근 실패: $firstErr")
            }
        }
        live.observe(owner, obs)
        onDispose { live.removeObserver(obs) }
    }
    return text
}
