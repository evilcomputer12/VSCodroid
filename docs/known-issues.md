# Known issues and verification limits

- Remote Docker requires an authorized SSH host and user-managed SSH credentials.
  Tablet-to-CachyOS SSH, Docker build, Compose, logs and cleanup passed. The
  configured LAN address may need updating after DHCP changes.
- Automatic IDE updates follow the Android-compatible VSCodroid server feed.
  New Microsoft releases can precede it. Changed Android patches or native
  libraries require a newer APK. Checks run while the IDE is open; see
  [IDE updates](ide-updates.md).
- Android limits child processes across apps. Running many Linux terminals and
  language servers alongside the original IDE can trigger phantom-process warnings.
  Stop unused sessions; terminal cleanup is bounded and checks process identity.
  This build does not disable Android process limits.
- Linux runs under PRoot, with tracing overhead and Android's kernel limits.
  systemd, privileged mounts, local Docker Engine and kernel namespaces are not
  supported. Native debuggers that require ptrace may conflict with PRoot.
- The VS Code extension host remains Android/Bionic. Linux executables and language
  servers need the provided runtime wrapper and a shared workspace path.
- Debian's Gradle package may be older than a project's wrapper. Prefer a project's
  checked-in Gradle wrapper for current Android/Java builds.
- Linux dashboard prose is English. Extension metadata follows the upstream editor
  locales; translations have not had native-speaker review.
- DNS defaults may need adjustment on VPN or enterprise networks.
- 256 Ki characters is the native clipboard write limit. Android may impose a
  smaller effective Binder limit depending on the clipboard payload.
- S Pen gestures, every physical keyboard layout, accessibility services, long
  background sessions, and Android version/device variants require broader testing.
- A host-side extraction of the real Debian tarball cannot preserve the image on a
  case-insensitive macOS filesystem (`PAM.7.gz` and `pam.7.gz` are distinct). Android
  extraction succeeded on its case-sensitive private storage.
- Rootfs home and projects live in this app's private storage and are erased on
  uninstall. Backup/export is the user's responsibility before removal.

This is an engineering build. Passing targeted tests on one tablet does not make
it a production-certified release. See the final report for measured results.
