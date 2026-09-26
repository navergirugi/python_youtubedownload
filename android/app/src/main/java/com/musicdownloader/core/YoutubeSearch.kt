package com.musicdownloader.core

import com.musicdownloader.util.Constants
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.schabi.newpipe.extractor.NewPipe
import org.schabi.newpipe.extractor.search.SearchInfo
import org.schabi.newpipe.extractor.stream.StreamInfo
import org.schabi.newpipe.extractor.stream.StreamInfoItem

// NewPipeExtractor-based search (yt-dlp ytsearchN 대체, JVM pure).
// scope='music'(기본): YouTube Music 필터 우선, 실패/0건이면 전체로 폴백.
object YoutubeSearch {
    const val SCOPE_MUSIC = "music"
    const val SCOPE_ALL = "all"

    suspend fun search(
        query: String,
        n: Int = Constants.YTSEARCH_N,
        scope: String = SCOPE_MUSIC,
        musicFilter: String = "music_songs",
    ): List<Candidate> = withContext(Dispatchers.IO) {
            val service = NewPipe.getService("YouTube")
        fun run(filter: List<String>): List<Candidate> {
            val qh = service.searchQHFactory.fromQuery(query, filter, "")
            val info = SearchInfo.getInfo(service, qh)
            return info.relatedItems
                .filterIsInstance<StreamInfoItem>()
                .take(n)
                .map {
                    Candidate(
                        title = it.name ?: "",
                        url = it.url ?: "",
                        channel = it.uploaderName ?: "",
                        durationStr = it.duration.let { d -> if (d > 0) "%d:%02d".format(d / 60, d % 60) else "" }
                    )
                }
        }
        if (scope == SCOPE_MUSIC) {
            try {
                val music = run(listOf(musicFilter))
                if (music.isNotEmpty()) return@withContext music
            } catch (_: Exception) { }
        }
        try {
            run(emptyList())
        } catch (e: Exception) {
            throw RuntimeException("검색 실패: ${e.message}")
        }
    }

    suspend fun fetchUrlMeta(url: String): Triple<String, String, String> =
        withContext(Dispatchers.IO) {
            val clean = UrlNormalize.cleanYoutubeUrl(url)
            try {
                val info = StreamInfo.getInfo(NewPipe.getService("YouTube"), clean)
                Triple(info.uploaderName ?: info.subChannelName ?: "", info.name ?: "", clean)
            } catch (_: Exception) {
                Triple("", "", clean)
            }
        }
}
