#!/usr/bin/env bash
set -euo pipefail

# Workspace and paths
WORKSPACE="${GITHUB_WORKSPACE:-$(pwd)}"
KERNEL_DIR="${KERNEL_DIR:-$WORKSPACE/kernel}"
SCRIPTS_DIR="${SCRIPTS_DIR:-$WORKSPACE/scripts}"
OUTDIR="${OUTDIR:-$WORKSPACE/out}"
NDKROOT="${NDKROOT:-${HOME}/android-ndk/android-ndk-r25c}"

mkdir -p "$OUTDIR"

echo "WORKSPACE: $WORKSPACE"
echo "KERNEL_DIR: $KERNEL_DIR"
echo "SCRIPTS_DIR: $SCRIPTS_DIR"
echo "OUTDIR: $OUTDIR"
echo "NDKROOT: $NDKROOT"

# 1) Obtain stock boot.img strictly from repo root (no URL)
BOOT_LOCAL="$WORKSPACE/boot.img"
if [[ ! -f "$BOOT_LOCAL" ]]; then
  echo "ERROR: boot.img not found at repository root: $BOOT_LOCAL" >&2
  exit 2
fi
cp -f "$BOOT_LOCAL" "$OUTDIR/boot.img"
echo "Using local boot image: $OUTDIR/boot.img"
file "$OUTDIR/boot.img" || true

# 2) Unpack boot image
mkdir -p "$OUTDIR/unpacked"
python3 "$SCRIPTS_DIR/unpack_bootimg.py" --input "$OUTDIR/boot.img" --outdir "$OUTDIR/unpacked"
ls -la "$OUTDIR/unpacked" || true

# 3) Extract kernel config (best-effort)
CONFIG_OUT="$OUTDIR/.config"
if [[ -f "$KERNEL_DIR/scripts/extract-ikconfig" ]]; then
  "$KERNEL_DIR/scripts/extract-ikconfig" "$OUTDIR/unpacked/"* > "$CONFIG_OUT" || true
else
  python3 "$SCRIPTS_DIR/extract_ikconfig.py" "$OUTDIR/unpacked/"* > "$CONFIG_OUT" || true
fi
if [[ ! -s "$CONFIG_OUT" ]]; then
  echo "No IKCONFIG found; falling back to device defconfig if present"
  if [[ -f "$KERNEL_DIR/arch/arm64/configs/flame_defconfig" ]]; then
    cp "$KERNEL_DIR/arch/arm64/configs/flame_defconfig" "$CONFIG_OUT"
  elif [[ -f "$KERNEL_DIR/arch/arm64/configs/flame-perf_defconfig" ]]; then
    cp "$KERNEL_DIR/arch/arm64/configs/flame-perf_defconfig" "$CONFIG_OUT"
  else
    echo "# fallback minimal config" > "$CONFIG_OUT"
  fi
fi
echo "Config stored at $CONFIG_OUT"

# 4) Apply KernelSU patches (best-effort; fail on patch errors)
pushd "$KERNEL_DIR" >/dev/null
if [[ -d "$WORKSPACE/kernelsu-next/patches" ]]; then
  echo "Applying KernelSU patches from kernelsu-next/patches..."
  for p in "$WORKSPACE"/kernelsu-next/patches/*.patch; do
    [[ -e "$p" ]] || continue
    echo "Applying $p"
    git apply --reject --whitespace=fix "$p"
  done
else
  echo "kernelsu-next/patches not found; skipping KernelSU patch application"
fi

# SUSFS integration placeholder (uncomment and adapt if you have patches)
# if [[ -d "$WORKSPACE/susfs4ksu-module/patches" ]]; then
#   echo "Applying SUSFS patches..."
#   for p in "$WORKSPACE"/susfs4ksu-module/patches/*.patch; do
#     [[ -e "$p" ]] || continue
#     echo "Applying $p"
#     git apply --reject --whitespace=fix "$p"
#   done
# fi
popd >/dev/null

# 5) Build kernel with Android NDK toolchain
if [[ ! -d "$NDKROOT" ]]; then
  echo "ERROR: NDKROOT does not exist: $NDKROOT" >&2
  exit 3
fi

export PATH="$NDKROOT/toolchains/llvm/prebuilt/linux-x86_64/bin:$PATH"
export ARCH=arm64
export SUBARCH=arm64
export CC=clang
export LLVM=1
export LLVM_IAS=1
export CROSS_COMPILE=aarch64-linux-android-
export CROSS_COMPILE_ARM32=arm-linux-androideabi-

KOUT="$OUTDIR/kernel_out"
mkdir -p "$KOUT"

# Choose a defconfig
if [[ -f "$KERNEL_DIR/arch/arm64/configs/flame_defconfig" ]]; then
  DEFCONFIG="flame_defconfig"
elif [[ -f "$KERNEL_DIR/arch/arm64/configs/flame-perf_defconfig" ]]; then
  DEFCONFIG="flame-perf_defconfig"
else
  echo "WARNING: flame(_perf)_defconfig not found, attempting olddefconfig with extracted .config"
  DEFCONFIG=""
fi

pushd "$KERNEL_DIR" >/dev/null
if [[ -n "$DEFCONFIG" ]]; then
  make O="$KOUT" ARCH=arm64 "$DEFCONFIG" -j"$(nproc)"
else
  cp "$CONFIG_OUT" "$KOUT/.config" || true
  make O="$KOUT" ARCH=arm64 olddefconfig -j"$(nproc)" || true
fi

make O="$KOUT" ARCH=arm64 -j"$(nproc)"
popd >/dev/null

# 6) Locate built kernel image
KERNEL_IMG=""
if [[ -f "$KOUT/arch/arm64/boot/Image.gz-dtb" ]]; then
  KERNEL_IMG="$KOUT/arch/arm64/boot/Image.gz-dtb"
elif [[ -f "$KOUT/arch/arm64/boot/Image.lz4-dtb" ]]; then
  KERNEL_IMG="$KOUT/arch/arm64/boot/Image.lz4-dtb"
elif [[ -f "$KOUT/arch/arm64/boot/Image" ]]; then
  KERNEL_IMG="$KOUT/arch/arm64/boot/Image"
fi

if [[ -z "$KERNEL_IMG" ]]; then
  echo "ERROR: Built kernel image not found in $KOUT/arch/arm64/boot" >&2
  ls -la "$KOUT/arch/arm64/boot" || true
  exit 4
fi
echo "Using built kernel image: $KERNEL_IMG"

# 7) Repack boot image
PATCHED_BOOT="$OUTDIR/boot_patched.img"
bash "$SCRIPTS_DIR/repack_boot.sh" --orig "$OUTDIR/boot.img" --kernel "$KERNEL_IMG" --out "$PATCHED_BOOT"

echo "Patched boot image created: $PATCHED_BOOT"
ls -la "$PATCHED_BOOT" || true
