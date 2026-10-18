package com.vscodroid.keyboard

import android.view.KeyEvent
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class LinuxShortcutsTest {
    @Test fun `command palette and save use explicit workbench commands`() {
        assertEquals("workbench.action.showCommands", workbenchShortcut("p", true, false, true, false))
        assertEquals("workbench.action.files.save", workbenchShortcut("s", true, false, false, false))
        assertNull(workbenchShortcut("c", true, false, false, false))
        assertNull(workbenchShortcut("p", true, true, false, false))
    }
    @Test fun `Android keycodes are distinct from DOM codes`() {
        assertEquals(KeyEvent.KEYCODE_P, nativeShortcutCode("p"))
        assertEquals(KeyEvent.KEYCODE_P, nativeShortcutCode("P"))
        assertEquals(KeyEvent.KEYCODE_F12, nativeShortcutCode("F12"))
        assertEquals(KeyEvent.KEYCODE_DPAD_LEFT, nativeShortcutCode("ArrowLeft"))
        assertNull(nativeShortcutCode("F13"))
        assertNull(nativeShortcutCode("世界"))
    }
}
