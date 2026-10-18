# VSCodroid Linux Edition — implementation report

Engineering build for the Samsung Galaxy Tab S10 Lite, 2026-10-18.
Source: `~/Development/VSCodroid-Linux`, branch `codex/linux-edition`.
Upstream base: `9f92ba7fc990d676b89fe854ef4b992bd891f737`.

## Delivered implementation

The fork uses `com.vscodroid.linux.debug` and separate private storage. It preserves
upstream's Code OSS interface, native Node backend, extension host and PTY. The
original `com.vscodroid` installation is untouched.

A bundled workspace extension provides Debian installation, progress and
cancellation, runtime health and storage diagnostics, persistent home/workspace,
Linux terminal profiles, build tasks, clangd configuration, terminal clipboard
controls and Docker-over-SSH contexts. A small browser extension routes fixed
Android toolbar actions through public workbench commands. Android modifier chords
and clipboard use the native event and origin-bound WebMessage paths.

Automatic IDE updates are enabled. A daily check downloads newer compatible Code
OSS releases, verifies their release digest and Android/native compatibility, and
queues activation for a full IDE restart. Trial startup has a health marker and
automatic rollback; manual recovery keeps the APK-bundled IDE available. See
[IDE updates](ide-updates.md) for release availability and compatibility limits.

Debian 13 ARM64 is downloaded from a versioned upstream image and verified against
its pinned SHA-256. Extraction is bounded and rejects traversal, duplicate files,
unsafe hard links and unexpected special files. Links are deferred until regular
files are written. Installation uses a lock, staging and an atomic completion
record. APT uses authenticated Debian repositories. Setup retries do not replace
home, projects or an existing root filesystem.

PRoot and its loader are packaged as Android-native executables in the APK. Guest
processes receive a clean environment and bind mounts for the persistent home and
workspace. There is no root requirement, SELinux change, exposed Docker socket or
local Docker Engine. PRoot provides userspace translation, not kernel isolation.

## Verification environment

- Host: Apple Silicon macOS, 8 GiB RAM, BellSoft JDK 21, NDK 27.2.12479018.
- Device: Samsung SM-X400, Android 16 / API 36, ARM64, 4 KiB pages.
- Gradle wrapper 9.7.1; Android Gradle Plugin 9.3.1; compile SDK 37.0.
- Upstream Code OSS 1.139.1 and Node 24.18.0; downloaded inputs passed their
  upstream checks. Native addons were cross-compiled with the Android NDK.
- Baseline APK built before the integration changes and launched alongside the
  original app. Baseline editor, command palette, quick open and PTY were tested.

## Results

| Area | Result and evidence |
|---|---|
| Android unit suite | 2,996 tests in the consolidated latest results: zero failures/errors, four skipped. The full run found one stale extension-inventory assertion; after correcting the inventory, that entire test class passed on rerun. The skips concern optional upstream C/C++ asset packs that are not part of this Debian build. |
| Installer/updater tests | 31 Python tests pass: extraction attacks, checksum, environment, working-directory boundaries, locking, release filtering, native compatibility and update scheduling. |
| Extension/bootstrap tests | 15 Node tests pass: Docker validation, argv preservation, escaping, IDE promotion, failed-trial rollback, APK changes, Android storage aliases, restored-terminal ownership, PID-reuse protection and path bounds. The upstream server bootstrap process/HTTP regression also passes. |
| Packaging gates | Build-step parity, binary inventory, native alignment/dependencies and license attribution pass. |
| Debian installation | Real pinned image verified and extracted on the tablet: 169,245,919 extracted regular-file bytes. Bash, ARM64 identity and APT probe passed under the app UID. |
| APT/toolchains | Signed Debian package installation passed. From the normal app terminal: C/GCC, C/Clang, C++, CMake/Make and Java compiled and ran; Python/Node Unicode, npm, Maven, Gradle, Git commit and OpenSSH checks passed. `output/toolchain-ui.log` ends with `TOOLCHAIN_SMOKE_OK`; exit 0. A separate Maven package and Gradle Java build both ran successfully and their compiled programs printed `JAVA_BUILD_OK 42`; `output/java-build-ui.log` records exit 0. Large real-world project builds remain outside this smoke test. |
| Native input/clipboard | Ctrl+Shift+P, Ctrl+P, Ctrl+Shift+F, Ctrl+S, undo/redo and Shift+arrow selection passed using injected Android events. Unicode/multiline and 112,500-character clipboard round trips passed; a foreign iframe received no clipboard reply. Editor paste/copy and terminal multiline paste/selection copy passed. This does not certify a physical keyboard or S Pen. |
| Integrated terminal/tasks/LSP | Normal app PTY ran all toolchains; native Ctrl+C reached a Python SIGINT handler; resize changed `stty size` from 10×164 to 45×164. A VS Code Linux task produced `LINUX_TASK_OK 49`. Real clangd initialize/hover/definition passed, and the editor displayed hover and completion for `square(int value)`. Python pdb evaluated 42. Restored terminals were adopted after a window reload; Stop Sessions removed their shell and PRoot process while retaining clangd. |
| Remote SSH | Existing Mac SSH configuration reached the authorized CachyOS host. With explicit approval, a dedicated tablet key was generated in app-private storage; only its public key was added to the host with forwarding/PTY restrictions. Tablet SSH authentication and Docker Engine 29.9.0 query passed. |
| Remote Docker build/Compose | Tablet uploaded a real build context, built an Alpine image, ran it with Compose, received Unicode logs and removed its own container/image. Exit 0, `REMOTE_DOCKER_SMOKE_OK` in `output/docker-ui.log`. Host inspection confirmed the test resources were gone. The saved `tablet-remote` context and dashboard connection check reached Engine 29.9.0. |
| IDE update mechanism | Real release download, digest/native compatibility checks and activation passed on the tablet. The promoted editor compiled C through its normal Linux terminal and reached Docker Engine 29.9.0. A health-check path-alias defect triggered the watchdog, which automatically restored the bundled IDE and blocked the failed digest; the fix has a regression test. After the fix, the promoted IDE wrote its healthy marker; the Restore Bundled IDE command queued and completed a return to the bundled tree. No newer compatible upstream release was available, so the staging test uses the actual current version, 1.139.1. |
| Tablet layout | Dashboard inspected at 1320×2112 portrait and 2112×1320 landscape. Buttons reflow and content scrolls within the editor; prior rotation settings were restored. |

Integrated toolchain, task, input, language-server and Docker checks ran from the
normal app process. ADB `run-as` was also used for setup, file evidence and
diagnostics; its different SELinux domain is not treated as proof of normal app
execution by itself.

## Artifacts and reproduction

Delivered app: **1.5.0-linux.6-debug**, version code **21**, package
`com.vscodroid.linux.debug`. The Linux extension is 0.3.0. The APK uses a local
debug signature, verified with Android `apksigner` (v2).

APK SHA-256:
`ab4faebf165d5e802e1f89e9161d6f64baa70e2f3e9b305dbc5666203203fee4`

The build-record check compares the APK's extension and server asset bytes with
the canonical source. Final packaging includes the tablet-verified path-alias
and terminal-cleanup fixes. `output/device-verification-summary.json` records the
machine-readable outcomes; individual evidence remains alongside it.

The delivered APK was installed and its on-device SHA-256 matched the artifact.
Its extracted updater/extension sources matched the canonical files. The final
normal app terminal compiled and ran the C sample, verified persistent home and
workspace data, and reached the saved Docker context; `final-install-ui.log` ends
with `DELIVERED_APK_OK` and exit 0. Native input/clipboard checks passed again, and
the manual IDE check reported the latest compatible version.

Run `scripts/build-linux.sh --prepare` for verified asset preparation and the
build, or omit `--prepare` for an already prepared tree. The script stages the
bundled extensions, runs Python/Node/Android tests, builds the debug APK and saves
`output/vscodroid-linux-debug.apk`, its SHA-256 and `linux-build-record.json`.

See [build and installation instructions](build-macos.md),
[runtime usage](linux-runtime.md), [keyboard](keyboard.md),
[clipboard](clipboard.md), [Docker](docker-remote.md) and
[test procedures](testing.md). Full evidence is retained under `output/`, including the consolidated
`output/android-final-test-results/` and the separate full-run/targeted-build logs.
The Gradle HTML report shows the most recent targeted invocation.

Signed package repositories can change. The rootfs is pinned; the build record
captures the shipped native binary hashes. This is a repeatable build procedure,
not a promise of future bit-identical outputs from unpinned APT/Termux indexes.
No production signing key was used and nothing was pushed or published.

## Limits

This remains an engineering debug build, not a production certification. PRoot
has tracing overhead and Android lifecycle/kernel restrictions. The extension
host remains Android/Bionic, so arbitrary Linux-native extensions do not work
without a runtime launcher. Native ptrace debugging requires separate validation;
Python pdb passed; Node inspector attach and native GDB attach remain unverified.

S Pen gestures, every physical keyboard layout, accessibility, long background
sessions, device/Android variants, low-storage behavior and interruption during
all APT maintainer scripts need broader testing. Dashboard prose is English;
metadata is localized but has not received native-speaker review. See
[known issues](known-issues.md) for storage, DNS and clipboard constraints.
