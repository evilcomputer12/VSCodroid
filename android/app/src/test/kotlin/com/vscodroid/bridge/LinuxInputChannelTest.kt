package com.vscodroid.bridge

import android.net.Uri
import io.mockk.every
import io.mockk.mockk
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class LinuxInputChannelTest {
    private fun origin(scheme: String = "http", host: String = "127.0.0.1", port: Int = 9443, user: String? = null): Uri =
        mockk<Uri>().also {
            every { it.scheme } returns scheme
            every { it.host } returns host
            every { it.port } returns port
            every { it.userInfo } returns user
        }
    @Test fun `clipboard accepts only top level exact editor origin`() {
        assertTrue(LinuxInputChannel.allowedOrigin(origin(), 9443, true))
        assertTrue(LinuxInputChannel.allowedOrigin(origin(host="localhost"), 9443, true))
        assertFalse(LinuxInputChannel.allowedOrigin(origin(), 9443, false))
        assertFalse(LinuxInputChannel.allowedOrigin(origin(port=9444), 9443, true))
        assertFalse(LinuxInputChannel.allowedOrigin(origin(host="127.0.0.1.evil.test"), 9443, true))
        assertFalse(LinuxInputChannel.allowedOrigin(origin(scheme="https"), 9443, true))
        assertFalse(LinuxInputChannel.allowedOrigin(origin(user="evil"), 9443, true))
    }
}
