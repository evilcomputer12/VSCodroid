package com.vscodroid.bridge

import android.net.Uri
import android.webkit.WebView
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import com.vscodroid.keyboard.KeyInjector
import com.vscodroid.keyboard.nativeShortcutCode
import org.json.JSONObject

/** Clipboard and IME chords are restricted to the exact top-level editor origin. */
object LinuxInputChannel {
    private const val NAME = "VSCodroidInput"
    private const val MAX_TEXT = 262144

    fun install(view: WebView, port: Int) {
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) return
        WebViewCompat.removeWebMessageListener(view, NAME)
        val origins = setOf("http://127.0.0.1:$port", "http://localhost:$port")
        val clipboard = ClipboardBridge(view.context)
        WebViewCompat.addWebMessageListener(view, NAME, origins) { _, message, origin, mainFrame, reply ->
            if (!allowedOrigin(origin, port, mainFrame)) return@addWebMessageListener
            val response = JSONObject()
            try {
                val data = message.data ?: return@addWebMessageListener
                if (data.length > MAX_TEXT + 1024) return@addWebMessageListener
                val request = JSONObject(data)
                response.put("id", request.optString("id"))
                when (request.getString("op")) {
                    "read" -> response.put("text", clipboard.readFromClipboard() ?: "")
                    "write" -> {
                        val text = request.getString("text")
                        require(text.length <= MAX_TEXT) { "Clipboard text exceeds 256 Ki characters" }
                        check(clipboard.copyToClipboard(text)) { "Android clipboard refused the write" }
                    }
                    "key" -> {
                        val key = request.getString("key")
                        require(nativeShortcutCode(key) != null) { "Unsupported native key" }
                        KeyInjector(view).injectKey(key, request.optBoolean("ctrlKey"),
                            request.optBoolean("altKey"), request.optBoolean("shiftKey"), request.optBoolean("metaKey"))
                    }
                    else -> error("Unsupported input operation")
                }
                response.put("ok", true)
            } catch (error: Exception) {
                response.put("ok", false).put("error", error.message ?: "Input operation failed")
            }
            reply.postMessage(response.toString())
        }
    }

    internal fun allowedOrigin(origin: Uri, port: Int, mainFrame: Boolean): Boolean =
        mainFrame && port > 0 && origin.scheme == "http" && origin.userInfo == null &&
            origin.port == port && origin.host in setOf("127.0.0.1", "localhost")
}
