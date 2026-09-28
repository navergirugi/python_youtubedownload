package com.musicdownloader.core

import android.content.ContentValues
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import com.arthenica.ffmpegkit.FFmpegKit
import com.arthenica.ffmpegkit.ReturnCode
import java.io.File

// 저장/변환 헬퍼.
// - 오디오: 원본 스트림(m4a/opus/webm)을 받아 MP3 로 변환한다. 유튜브는 MP3 를
//   serve 하지 않고 AAC/Opus 만 주므로, lame 인코딩뿐 아니라 디코딩도 반드시 필요하다.
// - 영상: progressive MP4 스트림을 그대로 저장 (합치기 불필요)
// - API 29+: MediaStore.Downloads 사용 (직접 파일 쓰기 차단 대응)
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

    /**
     * 받은 오디오(원본 컨테이너)를 MP3 로 변환한다.
     * @param bitrateK 128/192/320
     * @return 변환된 파일
     */
    fun toMp3(src: File, dst: File, bitrateK: Int): File {
        if (dst.exists() && dst.length() > 0) return dst
        // 유지보수 포크는 FFmpegKitConfig.Builder 를 제거했고 명령 문자열을 직접 받는다.
        val cmd = buildString {
            append("-y -i ").append(quote(src.absolutePath))
            append(" -vn -c:a libmp3lame -b:a ").append(bitrateK).append("k")
            append(" ").append(quote(dst.absolutePath))
        }
        val session = FFmpegKit.execute(cmd)
        val rc = session.returnCode
        val output = session.allLogsAsString ?: ""
        if (!ReturnCode.isSuccess(rc) || !dst.isFile || dst.length() == 0L) {
            dst.delete()
            throw RuntimeException(
                "MP3 변환 실패 (code=$rc): " + output.takeLast(300)
            )
        }
        return dst
    }

    private fun quote(p: String): String = "'" + p.replace("'", "'\\''") + "'"
}
