# Regression testing

## Automated host checks

```sh
python3 -m unittest discover -s tests/linux -v
node --test tests/linux/*.test.js
cd android
./gradlew assembleDebug testDebugUnitTest --max-workers=1 \
  -Dorg.gradle.jvmargs=-Xmx1024m -Pkotlin.compiler.execution.strategy=in-process
```

Python tests cover archive traversal, symlink/hardlink escapes, special files,
duplicates, extraction limits, setuid stripping, digest mismatch, HTTPS downgrade,
install locking, preserving existing installations, argv safety and environment
separation. Node tests cover Docker endpoint/context validation, argument handling
HTML escaping, restored-terminal ownership and PID-reuse protection. Kotlin tests cover shortcut routing and exact clipboard origin
restrictions alongside the upstream regression suite.

## Device checks

Use a dedicated fork installation, never the original app. This session uses a
Samsung SM-X400, Android 16 / API 36, ARM64, 4 KiB pages. APK native binaries are
checked for 16 KiB alignment as well.

```sh
python3 scripts/device-linux-smoke.py --serial DEVICE \
  --archive toolchains/linux/debian-trixie-arm64.tar.xz
python3 scripts/device-linux-smoke.py --serial DEVICE --action toolchains
```

These run under the debug app UID through `run-as`, whose SELinux domain differs
from a normal app process. They do not, alone, prove the integrated UI works.
Open the Linux terminal from the application and run the same checks there.
`tests/linux/toolchain-smoke.sh` compiles/runs C, C++, CMake and Java, runs Python,
Node, npm, Maven, Gradle, Git, OpenSSH, clangd, Docker CLI, Compose and Buildx. It
leaves its own test directory in the workspace for inspection.

For the debug WebView, forward its own `webview_devtools_remote_PID` socket to
localhost port 9222. `node scripts/webview-check.mjs` checks the workbench and
Ctrl+Shift+P / Ctrl+P with browser input events. Its `command`, `terminal`, and
`interrupt` actions exercise the command palette and PTY without printing the
server URL or connection token. Terminal input accepts one command; place
multiline shell scripts in workspace files and invoke them with bash. These are injected-key tests, not proof of a
physical keyboard or S Pen gesture.

## Manual matrix

- Physical Ctrl+Shift+P, Ctrl+P, Ctrl+Shift+F, Ctrl+S; undo/redo and selection.
- All extra-row quick actions with editor and terminal focus.
- Unicode and multiline clipboard in both directions; terminal selection;
  Ctrl+C interrupt without selection; 100 Ki-character clipboard round trip.
- Terminal resize (`stty size`), interactive application, Ctrl+C, stop/restart,
  portrait/landscape and external-keyboard connect/disconnect.
- Install cancellation and retry; low storage; interrupted APT configuration;
  home/workspace persistence after activity and server restart.
- Foreign iframe attempts to access the native clipboard channel must fail.
- Configure an authorized remote Docker host; verify SSH fingerprint and key
  authentication; `docker info`, build, Compose, logs and remote-volume behavior.

Do not report a case as passed merely because its implementation compiled.

## Reusable device checks

With the fork installed, first run `scripts/device-linux-smoke.py --serial SERIAL`
for a diagnostic under the app UID. That debug ADB process has a different SELinux
domain; repeat guest checks from the normal app terminal before claiming app support.
Copy `tests/linux/toolchain-smoke.sh` and `clangd-smoke.py` into the dedicated
`projects/.vscodroid-tests/` folder, then run:

```sh
bash /workspace/.vscodroid-tests/toolchain-smoke.sh
```

This creates a new test directory, compiles C/C++/CMake/Java, exercises Git,
Python/Node, checks build tools, completes a clangd initialize/hover/definition
exchange, exercises pdb, and validates a disposable Docker SSH context and Compose
configuration. It never contacts the placeholder Docker host.

For the debug WebView, forward local port 9222 to the app process's
`webview_devtools_remote_PID` socket. `node scripts/webview-check.mjs` tests the
workbench and command shortcuts. Run `eval tests/linux/webview-input-smoke.js`
for native bridge chords and clipboard round trips. Bring the app to the
foreground and close the notification shade first. The fixtures refuse to write
if the original plain-text clipboard cannot be read. With a **new empty disposable
text file focused**, `eval tests/linux/editor-input-smoke.js` tests editor paste,
copy, save, undo/redo and iframe clipboard denial. These clipboard checks restore
the original plain text in a `finally` block; use a test clipboard, because
non-text clip formats cannot be restored by the plain-text bridge. Never print
WebView connection URLs/tokens. Remove the ADB port forwarding after tests.

## IDE updater regression

Python tests verify channel selection, metadata filtering, digests, unsafe archive
rejection, native ABI/API compatibility, daily throttling and non-disruptive rollback.
Node tests exercise promotion, healthy restart, interrupted-trial rollback, invalid
paths, native path refresh and APK baseline changes. The bootstrap's existing
process/HTTP tests also run against the new loader.

`python3 scripts/device-ide-smoke.py --serial SERIAL` downloads and stages the
**current real release** through the installed updater, for a full-path regression
when no newer compatible release exists. Restart the debug fork, check its
workbench and terminal, wait for the healthy marker, then test Restore Bundled IDE
and restart again. This is an update mechanism test, not evidence of running a
newer IDE version. Keep tests in the dedicated debug package.

## Java builds and tablet layout

`tests/linux/java-build-smoke.sh` builds the same small Java program with Maven
and Gradle and executes both outputs. Run it from the normal Linux terminal.
`tests/linux/terminal-paste-smoke.js` exercises multiline terminal paste, and
`tests/linux/clangd-editor-smoke.js` checks the real editor completion UI.
These fixtures use disposable files in the shared test workspace.

With the Linux dashboard in front, run
`python3 scripts/device-layout-smoke.py --serial SERIAL` to capture portrait and
landscape. It verifies that the fork owns the foreground activity and restores
the tablet's prior rotation settings in a `finally` block. Inspect both images;
screenshot capture alone does not establish layout quality or S Pen behavior.
