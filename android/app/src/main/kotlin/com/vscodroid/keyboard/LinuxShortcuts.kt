package com.vscodroid.keyboard

import android.view.KeyEvent

/** Android key codes, never browser keyCode values. */
internal fun nativeShortcutCode(key: String): Int? = when {
    key.length == 1 && key[0].lowercaseChar() in 'a'..'z' ->
        KeyEvent.KEYCODE_A + (key[0].lowercaseChar() - 'a')
    key.length == 1 && key[0] in '0'..'9' -> KeyEvent.KEYCODE_0 + (key[0] - '0')
    key == "`" -> KeyEvent.KEYCODE_GRAVE
    key == " " -> KeyEvent.KEYCODE_SPACE
    key == "Enter" -> KeyEvent.KEYCODE_ENTER
    key == "Backspace" -> KeyEvent.KEYCODE_DEL
    key == "Delete" -> KeyEvent.KEYCODE_FORWARD_DEL
    key == "Tab" -> KeyEvent.KEYCODE_TAB
    key == "Escape" -> KeyEvent.KEYCODE_ESCAPE
    key == "ArrowUp" -> KeyEvent.KEYCODE_DPAD_UP
    key == "ArrowDown" -> KeyEvent.KEYCODE_DPAD_DOWN
    key == "ArrowLeft" -> KeyEvent.KEYCODE_DPAD_LEFT
    key == "ArrowRight" -> KeyEvent.KEYCODE_DPAD_RIGHT
    key.matches(Regex("F([1-9]|1[0-2])")) -> KeyEvent.KEYCODE_F1 + key.drop(1).toInt() - 1
    else -> null
}

/** Fixed toolbar actions use the public command API even when a terminal has focus. */
internal fun workbenchShortcut(key: String, ctrl: Boolean, alt: Boolean, shift: Boolean, meta: Boolean): String? {
    if (alt || meta) return null
    if (key == "F1" && !ctrl) return "workbench.action.showCommands"
    if (!ctrl) return null
    return when (key.lowercase()) {
        "p" -> if (shift) "workbench.action.showCommands" else "workbench.action.quickOpen"
        "f" -> if (shift) "workbench.action.findInFiles" else null
        "s" -> if (!shift) "workbench.action.files.save" else null
        "b" -> if (!shift) "workbench.action.toggleSidebarVisibility" else null
        "j" -> if (!shift) "workbench.action.togglePanel" else null
        "`" -> if (!shift) "workbench.action.terminal.toggleTerminal" else null
        else -> null
    }
}

/** evdev scan codes supply Chromium's KeyboardEvent.code alongside Android keyCode. */
internal fun nativeShortcutScanCode(key: String): Int {
    val letters = mapOf('a' to 30, 'b' to 48, 'c' to 46, 'd' to 32, 'e' to 18,
        'f' to 33, 'g' to 34, 'h' to 35, 'i' to 23, 'j' to 36, 'k' to 37,
        'l' to 38, 'm' to 50, 'n' to 49, 'o' to 24, 'p' to 25, 'q' to 16,
        'r' to 19, 's' to 31, 't' to 20, 'u' to 22, 'v' to 47, 'w' to 17,
        'x' to 45, 'y' to 21, 'z' to 44)
    if (key.length == 1) letters[key[0].lowercaseChar()]?.let { return it }
    return when (key) {
        "0" -> 11
        in "1".."9" -> if (key.length == 1) key.toInt() + 1 else 0
        "`" -> 41
        " " -> 57
        "Enter" -> 28
        "Backspace" -> 14
        "Delete" -> 111
        else -> 0
    }
}
