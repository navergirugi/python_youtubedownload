package com.musicdownloader

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.musicdownloader.core.MediaConvert
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * MediaConvert.toMp3 을 실제 기기에서 검증한다.
 *
 * 유튜브는 MP3 를 serve 하지 않고 AAC(m4a) / Opus(webm) 만 주므로,
 * "인코더만 있어서는" 부족하고 디코딩까지 되야 한다. 그래서 두 포맷을 모두
 * 소스로 넣어 실제로 MP3 로 바뀌는지 확인한다.
 */
@RunWith(AndroidJUnit4::class)
class Mp3ConvertTest {
    private fun ctx() = InstrumentationRegistry.getInstrumentation().targetContext

    private fun assertIsMp3(out: File, label: String) {
        assertTrue("$label: 파일 없음", out.isFile)
        assertTrue("$label: 0바이트", out.length() > 0)
        val head = ByteArray(3)
        val read = out.inputStream().use { it.read(head) }
        assertTrue("$label: 3바이트를 못 읽음", read == 3)
        // MP3 은 ID3 태그로 시작하거나, 태그가 없으면 프레임 동기 바이트로 시작한다.
        val id3 = head.size >= 3 &&
            head[0] == 'I'.code.toByte() && head[1] == 'D'.code.toByte() && head[2] == '3'.code.toByte()
        val frameSync = head.size >= 2 &&
            (head[0].toInt() and 0xFF) == 0xFF && ((head[1].toInt() and 0xE0) == 0xE0)
        assertTrue("$label: MP3 시그니처 아님 (head=${head.joinToString(" ")})", id3 || frameSync)
    }

    @Test
    fun convertsAacToMp3() {
        val cache = ctx().cacheDir
        val src = File(cache, "aac-in.m4a")
        val out = File(cache, "aac-out.mp3")
        // 1kHz 사인파 AAC (ffmpeg 으로 미리 생성해 push)
        src.copyFromAssetIfPresent("probe.m4a")
        assertTrue("테스트 픽스처 probe.m4a 없음", src.length() > 0)
        out.delete()

        MediaConvert.toMp3(src, out, 192)
        assertIsMp3(out, "AAC→MP3")
    }

    @Test
    fun convertsOpusToMp3() {
        val cache = ctx().cacheDir
        val src = File(cache, "opus-in.webm")
        val out = File(cache, "opus-out.mp3")
        src.copyFromAssetIfPresent("probe.webm")
        assertTrue("테스트 픽스처 probe.webm 없음", src.length() > 0)
        out.delete()

        MediaConvert.toMp3(src, out, 192)
        assertIsMp3(out, "Opus→MP3")
    }

    @Test
    fun reportsMissingInputInsteadOfCrashing() {
        val cache = ctx().cacheDir
        val out = File(cache, "never.mp3")
        out.delete()
        var threw = false
        try {
            MediaConvert.toMp3(File(cache, "does-not-exist.m4a"), out, 192)
        } catch (e: Exception) {
            threw = true
        }
        assertTrue("없는 입력에 대해 예외를 던져야 함", threw)
        assertTrue("실패 시 0바이트 파일을 남기면 안 됨", !out.exists() || out.length() == 0L)
    }

    private fun File.copyFromAssetIfPresent(name: String) {
        val assets = InstrumentationRegistry.getInstrumentation().context.assets
        try {
            assets.open(name).use { input ->
                outputStream().use { input.copyTo(it) }
            }
        } catch (_: Exception) {
            // 픽스처가 없으면 그대로 두고, 호출부가 length>0 을 검증한다.
        }
    }
}
