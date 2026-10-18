# Building on Apple Silicon macOS

Source: `~/Development/VSCodroid-Linux`, branch `codex/linux-edition`.
Upstream base: `9f92ba7fc990d676b89fe854ef4b992bd891f737`.

Install JDK 21, Android SDK command-line tools, Node.js, Python 3, Git, GitHub CLI,
GnuPG and CMake. This build used BellSoft JDK 21, Gradle's pinned 9.7.1 wrapper,
AGP 9.3.1 and NDK 27.2.12479018. NDK's macOS compiler requires Rosetta on ARM64.

```sh
export JAVA_HOME=$(/usr/libexec/java_home -v 21)
export ANDROID_HOME="$HOME/Library/Android/sdk"
export ANDROID_NDK_HOME="$ANDROID_HOME/ndk/27.2.12479018"
export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"
brew install gnupg cmake
sdkmanager 'platforms;android-37.0' 'build-tools;36.0.0' 'ndk;27.2.12479018'
cd ~/Development/VSCodroid-Linux
./scripts/build-linux.sh --prepare
```

For subsequent source changes, `./scripts/build-linux.sh` reuses the verified
asset tree. Do not run upstream `download-termux-tools.sh` alone afterward: it
replaces `usr/lib`; rerun PRoot preparation and all upstream shims afterward.

Output: `output/vscodroid-linux-debug.apk`, its SHA-256, build record and test logs.
Gradle unit reports: `android/app/build/reports/tests/testDebugUnitTest/index.html`.
The debug key is local Android debug signing only. No production key is used.

Use at least 12 GiB free for a cold build and preferably 16 GiB RAM. The supplied
build script limits Gradle to 1024 MiB / one worker, with the Kotlin compiler
in-process for an 8 GiB Mac, including the APK build that runs at the end of upstream asset preparation.

Build inputs are verified and pinned where upstream supplies pins. Termux and APT
repositories resolve signed current versions; this is reproducible preparation,
not a claim of bit-identical APKs across future repository changes. The build
record records the shipped binary hashes. Retain the signed package cache to
rebuild the same inputs (`TERMUX_OFFLINE=1`, subject to upstream freshness checks).

## Installation

```sh
adb devices -l
adb shell pm list packages com.vscodroid.linux.debug
# On a device without the fork installed:
adb install output/vscodroid-linux-debug.apk
adb shell am start -n com.vscodroid.linux.debug/com.vscodroid.SplashActivity
```

The original application is not replaced. Updating a prior fork requires the
same debug signer and `adb install -r` after the owner authorizes that update.
Do not uninstall to resolve a signature mismatch: uninstall erases private files.
On first launch finish core extraction; the Linux dashboard then appears in the
editor. Install Debian, check runtime health, and install development toolchains.
