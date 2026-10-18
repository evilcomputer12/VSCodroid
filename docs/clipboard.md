# Clipboard

The normal browser clipboard is attempted first. When WebView refuses its
permission, an AndroidX WebMessage request falls back to the Android clipboard.
The listener accepts only HTTP `127.0.0.1` or `localhost` at the active editor port,
with no userinfo, and only from the top-level frame. Foreign origins and child
frames cannot invoke it. The older bridge fallback remains session-token protected.

Requests have IDs and five-second deadlines. Native writes are limited to 256 Ki
characters to avoid oversized Binder transactions. Reads preserve plain-text
Unicode and line breaks and do not open `content://` clipboard documents.
The existing clipboard extraction implementation is retained.

Terminal Copy/Paste calls VS Code's terminal commands. Paste therefore preserves
xterm's multiline-paste prompt and bracketed-paste behavior, rather than sending
clipboard text as an unchecked shell command. Ctrl+C remains terminal interrupt
when nothing is selected. Clipboard contents and authentication tokens are not
written to application logs.
