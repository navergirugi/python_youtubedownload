package com.musicdownloader.util

// Port of config.py constants
object Constants {
    const val MELON_URL = "https://www.melon.com/chart/index.htm"
    const val YTSEARCH_N = 10
    const val AUDIO_QUERY_TEMPLATE = "{artist} {title} official audio"
    const val VIDEO_QUERY_TEMPLATE = "{artist} {title} official mv"
    val AUDIO_BITRATES = listOf("128", "192", "320")
    const val DEFAULT_AUDIO_BITRATE = "192"
    val VIDEO_QUALITIES = listOf("360p", "720p", "1080p", "best")
    const val DEFAULT_VIDEO_QUALITY = "720p"
    const val LOUDNORM_I = "-16"
    const val LOUDNORM_TP = "-1.5"
    const val LOUDNORM_LRA = "11"

    fun buildAudioQuery(artist: String, title: String): String =
        AUDIO_QUERY_TEMPLATE.replace("{artist}", artist.trim()).replace("{title}", title.trim()).split(Regex("\\s+")).joinToString(" ").trim()

    fun buildVideoQuery(artist: String, title: String): String =
        VIDEO_QUERY_TEMPLATE.replace("{artist}", artist.trim()).replace("{title}", title.trim()).split(Regex("\\s+")).joinToString(" ").trim()

    fun maxHeightForQuality(q: String): Int? = when (q) {
        "360p" -> 360
        "720p" -> 720
        "1080p" -> 1080
        else -> null
    }
}
