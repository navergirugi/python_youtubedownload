package com.musicdownloader.core

import java.io.File

// FFmpeg 없이 동작하는 저장 헬퍼 (v1).
// - 오디오: NewPipe 오디오 스트림을 원본 컨테이너 그대로 저장 (.m4a/.webm)
// - 영상: progressive MP4 스트림을 그대로 저장 (합치기 불필요)
// 데스크탑 MP3 변환/loudnorm은 v1 제한사항 (README-ANDROID 참고).
object MediaConvert {
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

    fun copyRaw(tmp: File, dst: File): String {
        if (dst.exists()) throw RuntimeException("이미 존재: ${dst.name}")
        tmp.copyTo(dst, overwrite = false)
        return dst.absolutePath
    }
}
