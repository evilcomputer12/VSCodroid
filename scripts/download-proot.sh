#!/usr/bin/env bash
# PRoot and its loader must be APK native executables, never chmod'ed downloads.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
WORK_DIR="$ROOT_DIR/toolchains/termux-packages"
ASSETS="$ROOT_DIR/android/app/src/main/assets/usr"
JNI="$ROOT_DIR/android/app/src/main/jniLibs/arm64-v8a"
. "$SCRIPT_DIR/lib/termux-packages.sh"
PACKAGES=(proot libtalloc libandroid-shmem termux-licenses)
termux_fetch_index
termux_resolve_packages resolved-proot.tsv "${PACKAGES[@]}"
termux_download_packages "${PACKAGES[@]}"
termux_extract_packages "${PACKAGES[@]}"
mkdir -p "$JNI" "$ASSETS/lib"
# This is the archive's layout, not a path used on the device.
PREFIX_IN_DEB=data/data/com.termux/files/usr
cp "$WORK_DIR/extracted/proot/$PREFIX_IN_DEB/bin/proot" "$JNI/libproot.so"
cp "$WORK_DIR/extracted/proot/$PREFIX_IN_DEB/libexec/proot/loader" "$JNI/libproot-loader.so"
for pkg in libtalloc libandroid-shmem; do
    for lib in "$WORK_DIR/extracted/$pkg/$PREFIX_IN_DEB/lib/"*.so*; do
        [ -e "$lib" ] && cp -L "$lib" "$ASSETS/lib/$(basename "$lib")"
    done
done
termux_copy_notices "$ASSETS" "${PACKAGES[@]}"
python3 "$SCRIPT_DIR/verify-android-elf.py" "$JNI/libproot.so" --lib-dir "$ASSETS/lib"
python3 "$SCRIPT_DIR/verify-android-elf.py" "$JNI/libproot-loader.so" --lib-dir "$ASSETS/lib"
