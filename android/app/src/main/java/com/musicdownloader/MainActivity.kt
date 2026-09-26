package com.musicdownloader

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.core.content.ContextCompat
import org.schabi.newpipe.extractor.NewPipe
import org.schabi.newpipe.extractor.downloader.Downloader
import org.schabi.newpipe.extractor.downloader.Request
import org.schabi.newpipe.extractor.downloader.Response
import org.schabi.newpipe.extractor.localization.Localization
import okhttp3.OkHttpClient
import okhttp3.Request as OkReq

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        initNewPipe()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            registerForActivityResult(ActivityResultContracts.RequestPermission()) {}.launch(
                Manifest.permission.POST_NOTIFICATIONS
            )
        }
        val sharedUrl = intent?.takeIf { it.action == android.content.Intent.ACTION_SEND }?.getStringExtra(android.content.Intent.EXTRA_TEXT) ?: ""
        setContent {
            MaterialTheme {
                Surface { AppNav(initialSharedUrl = sharedUrl) }
            }
        }
    }

    private fun initNewPipe() {
        try {
            val client = OkHttpClient()
            NewPipe.init(object : Downloader() {
                override fun execute(req: Request): Response {
                    val b = OkReq.Builder().url(req.url())
                    var hasUa = false
                    req.headers().forEach { (k, v) ->
                        if (k.equals("User-Agent", ignoreCase = true)) hasUa = true
                        v.forEach { b.header(k, it) }
                    }
                    if (!hasUa) {
                        b.header(
                            "User-Agent",
                            "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
                        )
                    }
                    req.dataToSend()?.let { b.post(okhttp3.RequestBody.create(null, it)) }
                    client.newCall(b.build()).execute().use { r ->
                        val body = r.body?.string() ?: ""
                        val headers = mutableMapOf<String, List<String>>()
                        r.headers.names().forEach { headers[it] = r.headers.values(it) }
                        return Response(r.code, r.message, headers, body, r.request.url.toString())
                    }
                }
            }, Localization.DEFAULT)
        } catch (_: Exception) { }
    }
}
