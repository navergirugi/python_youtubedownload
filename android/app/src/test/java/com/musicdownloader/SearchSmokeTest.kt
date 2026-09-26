package com.musicdownloader

import com.musicdownloader.core.YoutubeSearch
import kotlinx.coroutines.runBlocking
import okhttp3.OkHttpClient
import okhttp3.Request as OkReq
import okhttp3.RequestBody.Companion.toRequestBody
import org.junit.Assert.assertTrue
import org.junit.BeforeClass
import org.junit.Test
import org.schabi.newpipe.extractor.NewPipe
import org.schabi.newpipe.extractor.downloader.Downloader
import org.schabi.newpipe.extractor.downloader.Request
import org.schabi.newpipe.extractor.downloader.Response
import org.schabi.newpipe.extractor.localization.Localization

class SearchSmokeTest {
    companion object {
        @BeforeClass
        @JvmStatic
        fun init() {
            val client = OkHttpClient()
            NewPipe.init(object : Downloader() {
                override fun execute(req: Request): Response {
                    val b = OkReq.Builder().url(req.url())
                    req.headers().forEach { (k, v) -> v.forEach { b.header(k, it) } }
                    req.dataToSend()?.let { b.post(it.toRequestBody()) }
                    client.newCall(b.build()).execute().use { r ->
                        val body = r.body?.string() ?: ""
                        val headers = mutableMapOf<String, List<String>>()
                        r.headers.names().forEach { headers[it] = r.headers.values(it) }
                        return Response(r.code, r.message, headers, body, r.request.url.toString())
                    }
                }
            }, Localization.DEFAULT)
        }
    }

    @Test
    fun searchAllReturnsResults() {
        val res = runBlocking {
            YoutubeSearch.search("IU Celebrity official audio", 5, YoutubeSearch.SCOPE_ALL)
        }
        println("ALL: " + res.map { it.title })
        assertTrue("expected results, got $res", res.isNotEmpty())
    }

    @Test
    fun searchMusicFallsBackOrReturns() {
        val res = runBlocking {
            YoutubeSearch.search("IU Celebrity official audio", 5, YoutubeSearch.SCOPE_MUSIC, "music_songs")
        }
        println("MUSIC: " + res.map { it.title })
        assertTrue("expected results, got $res", res.isNotEmpty())
    }
}
