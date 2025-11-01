#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 --orig <orig_boot.img> --kernel <new_kernel_image> --out <patched_boot.img>" >&2
  exit 1
}

ORIG=""
KERNEL=""
OUT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --orig) ORIG="$2"; shift 2 ;;
    --kernel) KERNEL="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    *) usage ;;
  esac
done

[[ -n "$ORIG" && -n "$KERNEL" && -n "$OUT" ]] || usage

if [[ ! -f "$ORIG" ]]; then
  echo "ERROR: Original boot image not found: $ORIG" >&2
  exit 2
fi
if [[ ! -f "$KERNEL" ]]; then
  echo "ERROR: New kernel image not found: $KERNEL" >&2
  exit 3
fi

# Try abootimg path (works for legacy headers)
TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

echo "Attempting repack using abootimg..."
if abootimg -x "$ORIG" >/dev/null 2>&1; then
  # abootimg -x dumps into CWD; move them into TMP to avoid clutter
  for f in bootimg.cfg zImage initrd.img ramdisk.img ramdisk.cpio.gz initramfs.cpio.gz; do
    [[ -f "$f" ]] && mv "$f" "$TMP/" || true
  done
  if [[ -f "$TMP/bootimg.cfg" ]]; then
    # Determine ramdisk file
    RAMDISK=""
    for r in initrd.img ramdisk.img ramdisk.cpio.gz initramfs.cpio.gz; do
      if [[ -f "$TMP/$r" ]]; then
        RAMDISK="$TMP/$r"
        break
      fi
    done
    if [[ -z "$RAMDISK" ]]; then
      echo "ERROR: abootimg extracted no ramdisk file; cannot repack." >&2
      exit 4
    fi
    abootimg --create "$OUT" -f "$TMP/bootimg.cfg" -k "$KERNEL" -r "$RAMDISK"
    echo "Repacked with abootimg: $OUT"
    exit 0
  fi
fi

# If we reach here, abootimg path failed (likely modern header v3+).
echo "abootimg repack failed or unsupported header. This simple repacker does not handle modern AOSP header v3+."
echo "You will need a mkbootimg tool that matches your device's boot image header version."
exit 5
