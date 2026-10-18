# VSCodroid Linux Edition — progress

Started 2026-10-18. Upstream: `9f92ba7fc990d676b89fe854ef4b992bd891f737`.
Working branch: `codex/linux-edition`. No remote repository changes were made.

## Baseline and implementation

A baseline APK passed upstream packaging gates and was saved before integration.
It launched on the Samsung SM-X400 (Android 16, ARM64, 4 KiB pages), alongside the
untouched original `com.vscodroid`. The baseline frontend, Ctrl+Shift+P, Ctrl+P and
native PTY were exercised.

Implemented and locally committed the separate application identity, verified
Debian installer/launcher, Linux extension and dashboard, tasks/clangd/Docker
integration, native keyboard chords and trusted-origin clipboard channel.
The build now packages PRoot and its loader, runs the upstream binary/license
checks, and stages both Linux extensions from canonical sources.

## Build and host tests

The integrated debug APK built successfully. Consolidated Android results cover
2,996 tests, zero failures/errors and four optional-pack skips. The full run had
one stale inventory assertion; the corrected test class passed on rerun. The
installer/updater has 31 passing Python tests and extension/bootstrap has 15
passing Node tests.
Build-step parity, binary inventory and license attribution checks pass.

The Mac has 8 GiB RAM. An initial 4 GiB Gradle daemon caused excessive swap; builds
now use 1024 MiB, one worker and an in-process Kotlin compiler. Case-distinct
Debian man pages cannot be extracted
faithfully on the Mac's case-insensitive filesystem, so the real rootfs extraction
was verified on Android instead.

## Tablet and remote host

Debian's pinned image extracted successfully under the fork's app UID. APT used
signed HTTPS repositories, then completed installation of all requested compiler,
language, build, Git/SSH and Docker client packages. Runtime diagnostics found all
expected executables and Compose 2.26.1.

The user supplied the CachyOS SSH host and explicitly approved a dedicated tablet
key and temporary Docker tests. Only its public key was exported; the private key
stays in app-private Linux home. SSH authentication from the tablet and a query of
Docker Engine 29.9.0 succeeded. Normal app terminal, input and remote build/Compose
verification passed from the normal app process. Remote build contexts, Compose,
Unicode logs and scoped resource cleanup all passed. The saved Docker context is
configured. Clangd hover/completion, Linux tasks, terminal resize/signals and
editor/terminal clipboard checks also passed.

Evidence and final status are maintained in `docs/implementation-report.md` and
`output/`. No production release has been signed or published.

## Automatic IDE updates

Added the requested daily automatic update check, verified download and safe
staging, native/patch compatibility gates, startup health check and rollback.
The compatible feed currently publishes Code OSS 1.139.1; Microsoft desktop
1.142 is not substituted for an Android-patched server. New updater tests bring
the Python suite to 31 and Node suite to 15. The tablet downloaded and staged the
current real release, ran the promoted
editor, compiled C in Debian and reached the remote Docker Engine. A missed health
marker exposed Android storage aliases; the startup guard correctly restored the
bundled IDE. The alias fix passed its regression and tablet healthy-start test. Manual restore
also returned to the bundled IDE. Restored terminal adoption and process cleanup
passed after a window reload. An earlier
Android test run encountered temporary-directory failures when the host exhausted
disk space; the subsequent full run and targeted correction are preserved in
`output/android-final-test-results`.

## Delivered build

Version 1.5.0-linux.6-debug (code 21) is installed on the tablet. Its APK digest
and extracted extension/updater bytes match the deliverable. Final editor, native
clipboard, Debian compilation/persistence and saved Docker context checks passed.
The bundled IDE remains active with automatic updates enabled. The debug artifact,
checksum, build record, test evidence and full implementation report are complete.
