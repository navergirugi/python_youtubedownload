package com.musicdownloader.core

import android.net.Uri

// Port of search.py clean_youtube_url() + extract_youtube_url()
object UrlNormalize {
    private val VIDEO_ID = Regex("^[A-Za-z0-9_-]{6,}\$")
    private val URL_RE = Regex("https?://[^\\s\"'<>]+", RegexOption.IGNORE_CASE)

    fun cleanYoutubeUrl(raw: String): String {
        var u = raw.trim().trim('<', '>')
        if (u.isEmpty()) return u
        val withScheme = if ("://" in u) u else "https://$u"
        val uri = try { Uri.parse(withScheme) } catch (_: Exception) { return u }
        var host = (uri.host ?: "").lowercase()
        if (host.startsWith("www.")) host = host.removePrefix("www.")
        val vid = uri.getQueryParameter("v")
        if (vid != null && VIDEO_ID.matches(vid)) {
            return "https://www.youtube.com/watch?v=$vid"
        }
        val parts = (uri.path ?: "").split("/").filter { it.isNotEmpty() }
        if (host == "youtu.be" && parts.isNotEmpty() && VIDEO_ID.matches(parts[0])) {
            return "https://www.youtube.com/watch?v=${parts[0]}"
        }
        if (host in listOf("youtube.com", "music.youtube.com", "m.youtube.com") && parts.size >= 2) {
            if (parts[0] in listOf("shorts", "embed", "live", "v") && VIDEO_ID.matches(parts[1])) {
                return "https://www.youtube.com/watch?v=${parts[1]}"
            }
        }
        return u
    }

    fun extractYoutubeUrl(text: String): String {
        val m = URL_RE.find(text ?: "") ?: return ""
        val cleaned = cleanYoutubeUrl(m.value.trimEnd('.', ',', ';', ':', '!', '?', ')'))
        return if (cleaned.startsWith("https://www.youtube.com/watch?v=")) cleaned else ""
    }
}
