#!/bin/bash
#
# Repack Android boot image with a new kernel
# This script takes a new kernel image and the unpacked boot image components,
# and creates a new boot_patched.img file.
#

set -e

# Default values
KERNEL=""
UNPACKED_DIR=""
OUTPUT=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --kernel)
            KERNEL="$2"
            shift 2
            ;;
        --unpacked)
            UNPACKED_DIR="$2"
            shift 2
            ;;
        --out)
            OUTPUT="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 --kernel <kernel_image> --unpacked <unpacked_dir> --out <output_img>"
            exit 1
            ;;
    esac
done

# Validate arguments
if [ -z "$KERNEL" ] || [ -z "$UNPACKED_DIR" ] || [ -z "$OUTPUT" ]; then
    echo "Error: Missing required arguments"
    echo "Usage: $0 --kernel <kernel_image> --unpacked <unpacked_dir> --out <output_img>"
    exit 1
fi

if [ ! -f "$KERNEL" ]; then
    echo "Error: Kernel image not found: $KERNEL"
    exit 1
fi

if [ ! -d "$UNPACKED_DIR" ]; then
    echo "Error: Unpacked directory not found: $UNPACKED_DIR"
    exit 1
fi

INFO_FILE="$UNPACKED_DIR/bootimg.info"
if [ ! -f "$INFO_FILE" ]; then
    echo "Error: Boot image info file not found: $INFO_FILE"
    exit 1
fi

echo "Repacking boot image..."
echo "  Kernel: $KERNEL"
echo "  Unpacked dir: $UNPACKED_DIR"
echo "  Output: $OUTPUT"

# Read boot image parameters from info file
source "$INFO_FILE"

# Prepare arguments for mkbootimg
MKBOOTIMG_ARGS=""

# Add kernel
MKBOOTIMG_ARGS="$MKBOOTIMG_ARGS --kernel $KERNEL"

# Add ramdisk if present
RAMDISK="$UNPACKED_DIR/ramdisk.gz"
if [ -f "$RAMDISK" ]; then
    MKBOOTIMG_ARGS="$MKBOOTIMG_ARGS --ramdisk $RAMDISK"
fi

# Add second stage if present
SECOND="$UNPACKED_DIR/second"
if [ -f "$SECOND" ] && [ "$second_size" -gt 0 ]; then
    MKBOOTIMG_ARGS="$MKBOOTIMG_ARGS --second $SECOND"
fi

# Add device tree if present
DT="$UNPACKED_DIR/dt.img"
if [ -f "$DT" ] && [ -n "$dt_size" ] && [ "$dt_size" -gt 0 ]; then
    MKBOOTIMG_ARGS="$MKBOOTIMG_ARGS --dt $DT"
fi

# Add addresses and other parameters
if [ -n "$kernel_addr" ]; then
    MKBOOTIMG_ARGS="$MKBOOTIMG_ARGS --base 0x00000000 --kernel_offset $kernel_addr"
fi

if [ -n "$ramdisk_addr" ]; then
    MKBOOTIMG_ARGS="$MKBOOTIMG_ARGS --ramdisk_offset $ramdisk_addr"
fi

if [ -n "$second_addr" ] && [ "$second_size" -gt 0 ]; then
    MKBOOTIMG_ARGS="$MKBOOTIMG_ARGS --second_offset $second_addr"
fi

if [ -n "$tags_addr" ]; then
    MKBOOTIMG_ARGS="$MKBOOTIMG_ARGS --tags_offset $tags_addr"
fi

if [ -n "$page_size" ]; then
    MKBOOTIMG_ARGS="$MKBOOTIMG_ARGS --pagesize $page_size"
fi

if [ -n "$cmdline" ]; then
    MKBOOTIMG_ARGS="$MKBOOTIMG_ARGS --cmdline \"$cmdline\""
fi

if [ -n "$header_version" ]; then
    MKBOOTIMG_ARGS="$MKBOOTIMG_ARGS --header_version $header_version"
fi

if [ -n "$os_version" ]; then
    MKBOOTIMG_ARGS="$MKBOOTIMG_ARGS --os_version $os_version"
fi

# Add output file
MKBOOTIMG_ARGS="$MKBOOTIMG_ARGS --output $OUTPUT"

# Check if mkbootimg is available
if command -v mkbootimg >/dev/null 2>&1; then
    echo "Using mkbootimg to create boot image..."
    eval mkbootimg $MKBOOTIMG_ARGS
elif command -v abootimg >/dev/null 2>&1; then
    # Fallback to abootimg if mkbootimg is not available
    echo "Using abootimg to create boot image..."
    
    # Create a temporary config file for abootimg
    TMPCONF=$(mktemp)
    cat > "$TMPCONF" <<EOF
bootsize = 0x1000000
pagesize = $page_size
kerneladdr = $kernel_addr
ramdiskaddr = $ramdisk_addr
secondaddr = $second_addr
tagsaddr = $tags_addr
name = $name
cmdline = $cmdline
EOF
    
    # Use abootimg to create the boot image
    abootimg --create "$OUTPUT" -f "$TMPCONF" -k "$KERNEL" -r "$RAMDISK"
    rm -f "$TMPCONF"
else
    echo "Error: Neither mkbootimg nor abootimg found in PATH"
    echo "Attempting to use Python-based mkbootimg from Android tools..."
    
    # Try to find mkbootimg.py in common locations
    MKBOOTIMG_PY=""
    for path in /usr/bin/mkbootimg /usr/local/bin/mkbootimg ~/.local/bin/mkbootimg; do
        if [ -f "$path" ]; then
            MKBOOTIMG_PY="$path"
            break
        fi
    done
    
    if [ -z "$MKBOOTIMG_PY" ]; then
        # Create a minimal Python-based mkbootimg implementation
        echo "Creating boot image using Python implementation..."
        python3 - "$KERNEL" "$RAMDISK" "$OUTPUT" "$page_size" "$kernel_addr" "$ramdisk_addr" "$tags_addr" "$cmdline" <<'PYEOF'
import sys
import struct
import os

def pad_file(f, page_size):
    size = f.tell()
    remainder = size % page_size
    if remainder:
        padding = page_size - remainder
        f.write(b'\x00' * padding)

kernel_path = sys.argv[1]
ramdisk_path = sys.argv[2]
output_path = sys.argv[3]
page_size = int(sys.argv[4])
kernel_addr = int(sys.argv[5], 16) if sys.argv[5].startswith('0x') else int(sys.argv[5])
ramdisk_addr = int(sys.argv[6], 16) if sys.argv[6].startswith('0x') else int(sys.argv[6])
tags_addr = int(sys.argv[7], 16) if sys.argv[7].startswith('0x') else int(sys.argv[7])
cmdline = sys.argv[8].encode('utf-8') if len(sys.argv) > 8 else b''

# Read kernel and ramdisk
with open(kernel_path, 'rb') as f:
    kernel = f.read()
with open(ramdisk_path, 'rb') as f:
    ramdisk = f.read()

# Create boot image header
magic = b'ANDROID!'
kernel_size = len(kernel)
ramdisk_size = len(ramdisk)
second_size = 0
second_addr = 0
dt_size = 0

# Build header
header = struct.pack(
    '<8s10I16s512s32s1024sIQI',
    magic,
    kernel_size, kernel_addr,
    ramdisk_size, ramdisk_addr,
    second_size, second_addr,
    tags_addr, page_size,
    0,  # header_version
    0,  # os_version
    b'',  # name
    cmdline + b'\x00' * (512 - len(cmdline)),
    b'\x00' * 32,  # id
    b'\x00' * 1024,  # extra_cmdline
    0,  # recovery_dtbo_size
    0,  # recovery_dtbo_offset
    0   # header_size
)

# Write boot image
with open(output_path, 'wb') as out:
    out.write(header)
    pad_file(out, page_size)
    out.write(kernel)
    pad_file(out, page_size)
    out.write(ramdisk)
    pad_file(out, page_size)

print(f"Boot image created: {output_path}")
PYEOF
    else
        eval python3 "$MKBOOTIMG_PY" $MKBOOTIMG_ARGS
    fi
fi

if [ -f "$OUTPUT" ]; then
    echo "Boot image successfully created: $OUTPUT"
    ls -lh "$OUTPUT"
    exit 0
else
    echo "Error: Failed to create boot image"
    exit 1
fi
