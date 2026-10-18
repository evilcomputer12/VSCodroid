#!/usr/bin/env bash
# Full preparation: ./scripts/build-linux.sh --prepare
# Warm asset tree:  ./scripts/build-linux.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
export JAVA_HOME="${JAVA_HOME:-$(/usr/libexec/java_home -v 21)}"
export ANDROID_NDK_HOME="${ANDROID_NDK_HOME:-$ANDROID_HOME/ndk/27.2.12479018}"
export VSCODROID_NDK_VERSION="$(basename "$ANDROID_NDK_HOME")"
if [ "${1:-}" = --prepare ]; then
    GRADLE_OPTS="${GRADLE_OPTS:-} -Dorg.gradle.jvmargs=-Xmx1024m -Dorg.gradle.workers.max=1 -Dorg.gradle.project.kotlin.compiler.execution.strategy=in-process" ./scripts/build-all.sh
elif [ -n "${1:-}" ]; then
    echo 'Usage: scripts/build-linux.sh [--prepare]' >&2
    exit 2
fi
for binary in libnode.so libpython.so libproot.so libproot-loader.so; do
    test -s "android/app/src/main/jniLibs/arm64-v8a/$binary" || {
        echo "Missing $binary. Run scripts/build-linux.sh --prepare" >&2; exit 1;
    }
done
mkdir -p output
python3 scripts/stage-linux-extension.py
python3 -m unittest discover -s tests/linux -v 2>&1 | tee output/linux-python-tests.log
node --test tests/linux/*.test.js 2>&1 | tee output/linux-js-tests.log
(
    cd android
    ./gradlew assembleDebug testDebugUnitTest --console=plain --max-workers=1 \
        -Dorg.gradle.jvmargs='-Xmx1024m -Dfile.encoding=UTF-8' -Pkotlin.compiler.execution.strategy=in-process
) 2>&1 | tee output/linux-build.log
# A real copy: later Gradle builds must not mutate the delivered artifact.
cp android/app/build/outputs/apk/debug/app-debug.apk output/vscodroid-linux-debug.apk
shasum -a 256 output/vscodroid-linux-debug.apk > output/vscodroid-linux-debug.apk.sha256
python3 scripts/linux-build-record.py > output/linux-build-record.json
printf '\nAPK: %s/output/vscodroid-linux-debug.apk\n' "$ROOT"
