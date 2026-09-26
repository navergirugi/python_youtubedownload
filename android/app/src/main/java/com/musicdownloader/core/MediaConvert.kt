package com.musicdownloader.core

import android.content.ContentValues
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import java.io.File

// FFmpeg 없이 동작하는 저장 헬퍼 (v1).
// - 오디오: NewPipe 오디오 스트림을 원본 컨테이너 그대로 저장 (.m4a/.opus)
// - 영상: progressive MP4 스트림을 그대로 저장 (합치기 불필요)
// - API 29+: MediaStore.Downloads 사용 (직접 파일 쓰기 차단 대응)
// 데스크탑 MP3 변환/loudnorm은 v1 제한사항 (README-ANDROID 참고).
object MediaConvert {
    const val RELATIVE_DIR = "Download/MusicDownloader"

    fun extForAudio(codec: String?, fallbackSuffix: String?): String {
        val c = (codec ?: "").lowercase()
        val s = (fallbackSuffix ?: "").lowercase()
        return when {
            "mp4a" in c || s == "m4a" -> "m4a"
            "opus" in c -> "opus"
            "vorbis" in c -> "ogg"
            "mp3" in c || s == "mp3" -> "mp3"
            s.isNotBlank() -> s
            else -> "m4a"
        }
    }

    fun mimeForExt(ext: String): String = when (ext.lowercase()) {
        "m4a" -> "audio/mp4"
        "mp3" -> "audio/mpeg"
        "opus" -> "audio/opus"
        "ogg" -> "audio/ogg"
        "webm" -> "audio/webm"
        "mp4" -> "video/mp4"
        else -> "application/octet-stream"
    }

    /** API 26~28용 직접 저장. API 29+에서는 MediaStore를 쓸 것. */
    @Suppress("DEPRECATION")
    fun legacyDir(): File {
        val dir = File(
            Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS),
            "MusicDownloader"
        )
        dir.mkdirs()
        return dir
    }

    fun copyRaw(tmp: File, dst: File): String {
        if (dst.exists()) throw RuntimeException("이미 존재: ${dst.name}")
        tmp.copyTo(dst, overwrite = false)
        return dst.absolutePath
    }

    fun isMediaStore(): Boolean = Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q
}
