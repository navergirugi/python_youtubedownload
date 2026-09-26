package com.musicdownloader.core

import android.content.ContentValues
import android.content.Context
import android.os.Build
import android.provider.MediaStore
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import com.musicdownloader.util.Constants
import com.musicdownloader.util.Naming
import okhttp3.OkHttpClient
import okhttp3.Request
import org.schabi.newpipe.extractor.NewPipe
import org.schabi.newpipe.extractor.stream.StreamInfo
import java.io.File
import java.io.FileOutputStream

// 백그라운드 다운로드 (WorkManager).
// kind=audio|video, quality=128/192/320(오디오 소스 상한) or 360p/720p/1080p/best(영상 높이 상한)
// 저장: API 29+ MediaStore.Downloads/Download/MusicDownloader, 그 이하 직접 저장.
class DownloadWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result {
        val streamUrl = inputData.getString("watchUrl") ?: return Result.failure()
        val artist = inputData.getString("artist") ?: "Unknown"
        val title = inputData.getString("title") ?: "untitled"
        val kind = inputData.getString("kind") ?: "audio"
        val quality = inputData.getString("quality") ?: if (kind == "audio") Constants.DEFAULT_AUDIO_BITRATE else Constants.DEFAULT_VIDEO_QUALITY
        return try {
            val clean = UrlNormalize.cleanYoutubeUrl(streamUrl)
            if (clean.isEmpty()) return Result.failure(workDataOf("error" to "유효한 유튜브 URL이 아님 (검색 결과 URL 확인)"))
            val info = StreamInfo.getInfo(NewPipe.getService(0), clean)
            val base = Naming.songFilename(artist, title)
            val tmpRaw = File.createTempFile("dl", ".bin", applicationContext.cacheDir)
            try {
                val (ext, mime) = if (kind == "audio") {
                    val cap = (quality.toIntOrNull() ?: 192) * 1000
                    val audios = info.audioStreams ?: emptyList()
                    val picked = audios.filter { it.averageBitrate in 1..cap }.maxByOrNull { it.averageBitrate }
                        ?: audios.maxByOrNull { it.averageBitrate }
                        ?: return Result.failure(workDataOf("error" to "오디오 스트림 없음"))
                    downloadToFile(picked.content, tmpRaw)
                    val ext = try {
                        MediaConvert.extForAudio(picked.codec, picked.format?.suffix)
                    } catch (_: Exception) { "m4a" }
                    ext to MediaConvert.mimeForExt(ext)
                } else {
                    val maxH = Constants.maxHeightForQuality(quality)
                    val vids = info.videoStreams ?: emptyList()
                    val heightOf = { v: org.schabi.newpipe.extractor.stream.VideoStream ->
                        val h = try { v.height } catch (_: Exception) { -1 }
                        if (h > 0) h else Regex("(\\d{3,4})p").find(v.resolution ?: "")?.groupValues?.getOrNull(1)?.toIntOrNull() ?: Int.MAX_VALUE
                    }
                    val picked = vids.filter { maxH == null || heightOf(it) <= maxH }.maxByOrNull { heightOf(it) }
                        ?: vids.maxByOrNull { heightOf(it) }
                        ?: return Result.failure(workDataOf("error" to "비디오 스트림 없음"))
                    downloadToFile(picked.content, tmpRaw)
                    "mp4" to "video/mp4"
                }
                val fileName = "$base.$ext"
                val displayPath = if (MediaConvert.isMediaStore()) {
                    saveToMediaStore(fileName, mime, tmpRaw)
                } else {
                    val out = Naming.uniqueFile(MediaConvert.legacyDir(), base, ext)
                    MediaConvert.copyRaw(tmpRaw, out)
                    out.absolutePath
                }
                Result.success(workDataOf("path" to displayPath, "displayPath" to displayPath))
            } finally {
                tmpRaw.delete()
            }
        } catch (e: Exception) {
            Result.failure(workDataOf("error" to (e.message ?: "download failed")))
        }
    }

    private fun saveToMediaStore(fileName: String, mime: String, src: File): String {
        val resolver = applicationContext.contentResolver
        val values = ContentValues().apply {
            put(MediaStore.Downloads.DISPLAY_NAME, fileName)
            put(MediaStore.Downloads.MIME_TYPE, mime)
            put(MediaStore.Downloads.RELATIVE_PATH, MediaConvert.RELATIVE_DIR)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                put(MediaStore.Downloads.IS_PENDING, 1)
            }
        }
        val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
            ?: throw RuntimeException("MediaStore 저장 실패 (Download 권한 확인)")
        try {
            resolver.openOutputStream(uri)?.use { out ->
                src.inputStream().use { it.copyTo(out) }
            } ?: throw RuntimeException("MediaStore 쓰기 실패")
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val done = ContentValues().apply { put(MediaStore.Downloads.IS_PENDING, 0) }
                resolver.update(uri, done, null, null)
            }
        } catch (e: Exception) {
            resolver.delete(uri, null, null)
            throw e
        }
        return "${MediaConvert.RELATIVE_DIR}/$fileName"
    }

    private fun downloadToFile(url: String, dst: File) {
        val client = OkHttpClient()
        val req = Request.Builder().url(url).header("User-Agent", "Mozilla/5.0").build()
        client.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) throw RuntimeException("HTTP ${resp.code}")
            val body = resp.body ?: throw RuntimeException("empty body")
            val total = body.contentLength()
            body.byteStream().use { ins ->
                FileOutputStream(dst).use { out ->
                    val buf = ByteArray(64 * 1024)
                    var done = 0L
                    while (true) {
                        val r = ins.read(buf)
                        if (r < 0) break
                        out.write(buf, 0, r)
                        done += r
                        if (total > 0) setProgressAsync(workDataOf("progress" to ((done * 100 / total).toInt().coerceIn(0, 100))))
                    }
                }
            }
        }
    }
}
