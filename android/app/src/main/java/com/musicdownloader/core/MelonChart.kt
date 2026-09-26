package com.musicdownloader.core

import org.jsoup.Jsoup
import org.jsoup.nodes.Document
import org.jsoup.nodes.Element
import org.jsoup.select.Elements
import java.io.IOException
import java.nio.charset.StandardCharsets
import java.util.concurrent.TimeUnit
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response

/**
 * Melon TOP100 chart fetching and manual parsing.
 * Port of melon.py logic to Kotlin using Jsoup + OkHttp.
 */
object MelonChart {

    private const val MELON_URL = "https://www.melon.com/chart/index.htm"
    private const val USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    private const val REFERER = "https://www.melon.com/"
    private const val ACCEPT_LANGUAGE = "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    private const val TIMEOUT_SECONDS = 15L
    private const val MIN_HTML_LENGTH = 5000

    private val client = OkHttpClient.Builder()
        .connectTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .readTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .writeTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .followRedirects(true)
        .build()

    /**
     * Fetches the current Melon TOP100 chart.
     * @return List of up to 100 SongEntry objects
     * @throws MelonBlockedException on HTTP error, empty response, or parse failure
     */
    @Throws(MelonBlockedException::class)
    fun fetchTop100(): List<SongEntry> {
        val request = Request.Builder()
            .url(MELON_URL)
            .header("User-Agent", USER_AGENT)
            .header("Referer", REFERER)
            .header("Accept-Language", ACCEPT_LANGUAGE)
            .build()

        val response: Response
        try {
            response = client.newCall(request).execute()
        } catch (e: IOException) {
            throw MelonBlockedException("멜론 접속 실패: ${e.message}")
        }

        if (!response.isSuccessful) {
            response.close()
            throw MelonBlockedException("멜론 차단/비정상 응답: status=${response.code}")
        }

        val html = response.body?.string() ?: ""
        response.close()

        if (html.length < MIN_HTML_LENGTH) {
            throw MelonBlockedException("멜론 차단/비정상 응답: HTML 너무 짧음 (${html.length} chars)")
        }

        val songs = parseChartHtml(html)
        if (songs.isEmpty()) {
            throw MelonBlockedException("멜론 파싱 결과 0건 (차단 또는 셀렉터 변경)")
        }

        return songs.take(100)
    }

    /**
     * Parses chart HTML from Melon.
     * Selector: tr[data-song-no] → .ellipsis.rank01 a (title) + .ellipsis.rank02 a (artist, split by comma first)
     */
    private fun parseChartHtml(html: String): List<SongEntry> {
        val doc: Document = Jsoup.parse(html)
        val rows: Elements = doc.select("tr[data-song-no]")
        val result = mutableListOf<SongEntry>()

        for (tr in rows) {
            val titleEl: Element? = tr.selectFirst(".ellipsis.rank01 a")
            val artistEl: Element? = tr.selectFirst(".ellipsis.rank02 a")

            if (titleEl == null || artistEl == null) continue

            val title = titleEl.text().trim()
            val artistRaw = artistEl.text().trim()
            val artist = artistRaw.split(",").first().trim()

            if (title.isNotEmpty() && artist.isNotEmpty()) {
                result.add(SongEntry(artist = artist, title = title))
            }
        }

        return result
    }

    /**
     * Parses manual input lines supporting two formats:
     * - "가수 - 제목" (dash separator)
     * - "가수,제목" (comma separator, only when no dash present)
     * Returns pair of (valid songs, error lines)
     */
    fun parseManualLines(text: String): Pair<List<SongEntry>, List<String>> {
        val songs = mutableListOf<SongEntry>()
        val errors = mutableListOf<String>()

        text.lines().forEach { line ->
            val trimmed = line.trim()
            if (trimmed.isEmpty()) return@forEach

            val parts: List<String>
            if (trimmed.contains(",") && !trimmed.contains(" - ")) {
                parts = trimmed.split(",", limit = 2).map { it.trim() }
            } else if (trimmed.contains(" - ")) {
                parts = trimmed.split(" - ", limit = 2).map { it.trim() }
            } else {
                errors.add(trimmed)
                return@forEach
            }

            if (parts.size == 2 && parts[0].isNotEmpty() && parts[1].isNotEmpty()) {
                songs.add(SongEntry(artist = parts[0], title = parts[1]))
            } else {
                errors.add(trimmed)
            }
        }

        return Pair(songs, errors)
    }

    /**
     * Parses manual input from a file.
     */
    @Throws(IOException::class)
    fun parseManualFile(filePath: String): Pair<List<SongEntry>, List<String>> {
        val text = java.io.File(filePath).readText(StandardCharsets.UTF_8)
        return parseManualLines(text)
    }
}

/**
 * Exception thrown when Melon chart fetching fails or is blocked.
 */
class MelonBlockedException(message: String) : RuntimeException(message)

/**
 * Data class matching models.py SongEntry.
 * Immutable, with query templates for audio/video search.
 */
data class SongEntry(
    val artist: String,
    val title: String
) {
    companion object {
        const val AUDIO_QUERY_TEMPLATE = "{artist} {title} official audio"
        const val VIDEO_QUERY_TEMPLATE = "{artist} {title} official mv"
    }

    fun queryAudio(): String = AUDIO_QUERY_TEMPLATE
        .replace("{artist}", artist)
        .replace("{title}", title)

    fun queryVideo(): String = VIDEO_QUERY_TEMPLATE
        .replace("{artist}", artist)
        .replace("{title}", title)
}
