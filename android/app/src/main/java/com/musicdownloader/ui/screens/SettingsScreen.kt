package com.musicdownloader.ui.screens

import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.ui.zIndex
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import com.musicdownloader.store.MenuOrderStore
import kotlinx.coroutines.launch
import java.util.Collections
import kotlin.math.roundToInt

// 데스크탑 "메뉴 순서: 사이드바 드래그 변경" 포팅.
// 항목 롱프레스 후 위/아래 드래그 → 순서 저장 (설정은 항상 마지막 고정).
@Composable
private fun MenuOrderEditor() {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    val saved by MenuOrderStore.flow(ctx).collectAsState(initial = MenuOrderStore.DEFAULT)

    var order by remember { mutableStateOf(MenuOrderStore.DEFAULT) }
    var synced by remember { mutableStateOf(false) }
    LaunchedEffect(saved) {
        if (!synced) { order = saved; synced = true }
    }

    var dragKey by remember { mutableStateOf<String?>(null) }
    var startIdx by remember { mutableStateOf(0) }
    var yOff by remember { mutableFloatStateOf(0f) }
    val rowPx = with(LocalDensity.current) { 64.dp.toPx() }

    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text("메뉴 순서 (길게 눌러 드래그)", style = MaterialTheme.typography.titleMedium)
        Text("설정은 항상 마지막에 고정됩니다.", style = MaterialTheme.typography.bodySmall)
        order.forEachIndexed { idx, key ->
            val dragging = key == dragKey
            ListItem(
                modifier = Modifier
                    .zIndex(if (dragging) 1f else 0f)
                    .graphicsLayer {
                        translationY = if (dragging) yOff else 0f
                        shadowElevation = if (dragging) 8f else 0f
                    }
                    .pointerInput(key) {
                        detectDragGesturesAfterLongPress(
                            onDragStart = {
                                dragKey = key
                                startIdx = order.indexOf(key)
                                yOff = 0f
                            },
                            onDragEnd = {
                                dragKey = null
                                yOff = 0f
                                scope.launch { MenuOrderStore.save(ctx, order) }
                            },
                            onDragCancel = {
                                dragKey = null
                                yOff = 0f
                            },
                            onDrag = { change, amt ->
                                change.consume()
                                yOff += amt.y
                                val from = order.indexOf(key)
                                if (from < 0) return@detectDragGesturesAfterLongPress
                                val target = (startIdx + (yOff / rowPx).roundToInt())
                                    .coerceIn(0, order.lastIndex)
                                if (target != from) {
                                    order = order.toMutableList().also {
                                        Collections.swap(it, from, target)
                                    }
                                }
                            }
                        )
                    },
                headlineContent = { Text("${idx + 1}. ${MenuOrderStore.LABELS[key] ?: key}") },
                trailingContent = { Icon(Icons.Default.Menu, contentDescription = "드래그") }
            )
            if (idx < order.lastIndex) HorizontalDivider()
        }
        OutlinedButton(onClick = {
            order = MenuOrderStore.DEFAULT
            scope.launch { MenuOrderStore.save(ctx, MenuOrderStore.DEFAULT) }
        }) { Text("순서 초기화") }
    }
}

@Composable
fun SettingsScreen() {
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item { MenuOrderEditor() }
        item { HorizontalDivider() }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("저장 위치·정보", style = MaterialTheme.typography.titleLarge)
                Text("음원/영상: Download/MusicDownloader (앱 재설치에도 유지)")
                Text("데스크탑 설정(~/.musicdownloader.json)과 별개로 동작합니다.")
                Text("업데이트: GitHub Release에서 MusicDownloader-android.apk 수동 다운로드 (sideload).")
                Text("Play 스토어 배포 불가: YouTube 다운로드 TOS 위반 소지 → 사이드로드 전용.")
            }
        }
    }
}
