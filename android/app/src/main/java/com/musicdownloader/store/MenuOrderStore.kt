package com.musicdownloader.store

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

// 데스크탑 config.py get_menu_order/set_menu_order 포팅.
// 설정 탭은 항상 마지막에 고정 (데스크탑과 동일).
private val Context.dataStore by preferencesDataStore("settings")

object MenuOrderStore {
    private val KEY = stringPreferencesKey("menu_order")

    // MP3, MP4, TOP100, URL (요청: TOP100은 MP4 다음)
    val DEFAULT = listOf("audio", "video", "top100", "url")

    val LABELS = mapOf(
        "top100" to "TOP100",
        "audio" to "MP3",
        "video" to "MP4",
        "url" to "URL",
    )

    fun flow(ctx: Context): Flow<List<String>> =
        ctx.dataStore.data.map { prefs ->
            val raw = prefs[KEY]?.split(",")?.map { it.trim() }?.filter { it in LABELS } ?: emptyList()
            if (raw.size == DEFAULT.size && raw.sorted() == DEFAULT.sorted()) raw else DEFAULT
        }

    suspend fun save(ctx: Context, order: List<String>) {
        val clean = order.filter { it in LABELS }
        if (clean.size != DEFAULT.size || clean.sorted() != DEFAULT.sorted()) return
        ctx.dataStore.edit { it[KEY] = clean.joinToString(",") }
    }
}
