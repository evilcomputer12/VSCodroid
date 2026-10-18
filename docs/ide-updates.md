# Automatic IDE updates

Automatic Code OSS updates are enabled by default. The Linux extension checks
one minute after the editor opens, then every six hours, with a persisted daily
network-check limit. This runs while the IDE is open; it does not wake a closed
Android app. Disable **VSCodroid Linux: Auto Update IDE** in user settings to stop
automatic checks. **Linux: Check IDE Updates** performs an immediate check.

The release source is the existing `server-X.Y.Z` channel in
<https://github.com/rmyndharis/VSCodroid/releases>. These are MIT Code OSS builds
with Android patches. Microsoft desktop/server downloads are not interchangeable
with this Android runtime. As checked on 2026-10-18, the compatible channel's
newest published server is 1.139.1; Microsoft's stable release is 1.142.0.

The updater automatically downloads a newer stable-source ARM64 server, checks
the GitHub release asset SHA-256 and size, extracts into a bounded private staging
directory, and checks the Android patch hashes and native package compatibility.
The release metadata and digest are trusted through HTTPS from the upstream
GitHub repository; they are not a separate publisher signature. Tar links,
devices, duplicate entries and escaping paths are rejected. Node's required ABI
is read from `remote/.npmrc` at the immutable Microsoft source commit recorded in
the verified tree. Native implementations remain the ones shipped in the APK.
Other native payloads must match the APK byte for byte. A patch, native API or ABI
change requires a newer app build and is reported in the dashboard.

A verified update is queued, without interrupting the current editor or its
terminals. Fully stop the fork using its server notification, then launch it to
activate the update. A window reload alone keeps the current server. The bundled
IDE, Debian filesystem, Linux home, user extensions and projects are preserved.
The updater needs approximately 1.6 GiB of free space for a download and staging.

The first updated launch is a trial. The Linux extension records health after
30 seconds of activation. If that does not happen within three minutes, the
bootstrap ends the failed server; the existing Android watchdog restarts with
the previous version. A process death before the health marker also causes
rollback on the next start. The failed digest is blocked from automatic retries.
This is a startup health check, not proof that every extension or future feature
works. **Linux: Restore Bundled IDE** schedules manual rollback for the next full
start. Installing a newer APK resets the compatibility baseline to its bundled
IDE. Old inactive update caches are removed by a subsequent download check.

Status lives in `files/server/ide-updates/status.json`; the dashboard and Linux
output channel display it. Offline, quota, compatibility, storage and checksum
errors leave the current IDE working. Downloads use a single-writer lock and
bounded timeouts. Settings are application-scoped, so a workspace cannot enable
updates or redirect their source.

Future compatible release availability is controlled by upstream. This fork has
not been published and no release-upload credentials or automation were created.
See the implementation report for the actual host and tablet update tests.
