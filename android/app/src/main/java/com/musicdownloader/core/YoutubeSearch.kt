package com.musicdownloader.core

import com.musicdownloader.util.Constants
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.schabi.newpipe.extractor.NewPipe
import org.schabi.newpipe.extractor.search.SearchInfo
import org.schabi.newpipe.extractor.stream.StreamInfo
import org.schabi.newpipe.extractor.stream.StreamInfoItem

// NewPipeExtractor-based search (yt-dlp ytsearchN 대체, JVM pure)
object YoutubeSearch {
    suspend fun search(query: String, n: Int = Constants.YTSEARCH_N): List<Candidate> =
        withContext(Dispatchers.IO) {
            val service = NewPipe.getService(0)
            val qh = service.searchQHFactory.fromQuery(query, emptyList(), "")
            val info = SearchInfo.getInfo(service, qh)
            info.relatedItems
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

    suspend fun fetchUrlMeta(url: String): Triple<String, String, String> =
        withContext(Dispatchers.IO) {
            val clean = UrlNormalize.cleanYoutubeUrl(url)
            try {
                val info = StreamInfo.getInfo(NewPipe.getService(0), clean)
                Triple(info.uploaderName ?: info.subChannelName ?: "", info.name ?: "", clean)
            } catch (_: Exception) {
                Triple("", "", clean)
            }
        }
}
