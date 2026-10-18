# Linux Edition architecture

The fork retains upstream's Kotlin shell, WebView, Code OSS 1.139.1, native Android
Node.js, node-pty and extension host. Its application ID is
`com.vscodroid.linux.debug`; the original `com.vscodroid` has separate storage.

`linux/extension` is a bundled workspace extension, staged by
`scripts/stage-linux-extension.py`. It provides a responsive runtime dashboard,
setup progress/cancellation, diagnostics, terminal profiles, build tasks and Docker
contexts. `linux/ui` is a browser extension that executes a small allowlist of
public VS Code commands for native toolbar actions. Neither opens a network service.

The Python installer uses the APK's existing native Python. It verifies the
pinned Debian ARM64 image, extracts into a fresh staging directory with bounded
size/member counts, defers links, refuses traversal and special files outside
`dev`, strips setuid/setgid, and atomically promotes the result. Home and workspace
live outside the root filesystem. A file lock prevents simultaneous installations.

`libproot.so` and `libproot-loader.so` are Android ARM64 executables packaged in
`jniLibs`, installed by Android with executable permissions. The Termux package
index is signature-verified and each package is digest-verified. No runtime path
assumes a Termux installation. PRoot's documented loader maps the Debian programs;
the app does not alter SELinux, system partitions, target SDK, or Android's seccomp
policy. `PROOT_NO_SECCOMP=1` disables PRoot's optional tracing acceleration only.

Linux terminals use VS Code's existing real PTY. Native Python replaces itself
with PRoot using `execve`, preserving the PTY, window-size changes, and signals.
`--kill-on-exit` contains the lifetime of guest child processes. The guest receives
a clean environment, excluding Android's Bionic preloads and Node/Python options.
Restored terminals are recognized by their own live PRoot executable and rootfs
when VS Code omits their original creation options. Closing a managed terminal
allows a brief graceful exit, then ends a remaining tracer and its tracees. The
fallback checks the process start identity to avoid acting on a reused PID.
PRoot emulates UID 0 for package tools; it grants no kernel privileges and is not
a security boundary between untrusted programs running as the same app UID.

The workspace is bound at both `/workspace` and its identical Android absolute
path, so compiler diagnostics and Linux tasks refer to files the editor can open.
The extension host remains Android/Bionic. Linux language servers must be started
through the runtime launcher; arbitrary glibc extensions are not automatically
made Android-compatible.

Clipboard and IME chords use an AndroidX WebMessage listener restricted to the
current loopback editor origin and top-level frame. Toolbar commands use the
browser extension API. Upstream token-protected clipboard fallback and navigation
handling remain for compatibility.

## IDE update lifecycle

The extension's daily updater reads the upstream VSCodroid server release feed,
verifies and adapts compatible Code OSS archives, and queues a separate server
tree. The bootstrap selects it only at a full server start, binds APK-native
executables, and records the running tree for Kotlin's orphan-server identity
check. Extension-host activation earns a health marker; failed trials fall back
on the next watchdog restart. The APK's original server is retained for manual
recovery. See [automatic updates](ide-updates.md) for trust, compatibility and
release-channel limits.
