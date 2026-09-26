package com.musicdownloader.util

// Port of naming.py
object Naming {
    private val ILLEGAL = Regex("""[\\/:*?"<>|]""")

    fun sanitize(name: String): String {
        var s = ILLEGAL.replace(name, "")
        s = s.trim().trim('.')
        s = s.replace(Regex("\\s+"), " ")
        return s
    }

    fun songFilename(artist: String, title: String): String =
        sanitize("$artist - $title")

    fun uniqueFile(dir: java.io.File, base: String, ext: String): java.io.File {
        val e = if (ext.startsWith(".")) ext else ".$ext"
        val safe = sanitize(base)
        var f = java.io.File(dir, "$safe$e")
        var i = 1
        while (f.exists()) {
            f = java.io.File(dir, "$safe ($i)$e")
            i++
        }
        return f
    }
}
