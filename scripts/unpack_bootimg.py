#!/usr/bin/env python3
"""
Unpack Android boot image into its components.
This script extracts the kernel, ramdisk, and other components from a boot.img file.
"""

import argparse
import os
import struct
import sys


class BootImageHeader:
    """Android boot image header structure."""
    
    BOOT_MAGIC = b'ANDROID!'
    BOOT_MAGIC_SIZE = 8
    BOOT_NAME_SIZE = 16
    BOOT_ARGS_SIZE = 512
    BOOT_EXTRA_ARGS_SIZE = 1024
    
    def __init__(self):
        self.kernel_size = 0
        self.kernel_addr = 0
        self.ramdisk_size = 0
        self.ramdisk_addr = 0
        self.second_size = 0
        self.second_addr = 0
        self.tags_addr = 0
        self.page_size = 0
        self.dt_size = 0
        self.os_version = 0
        self.name = b''
        self.cmdline = b''
        self.id = b''
        self.extra_cmdline = b''
        self.recovery_dtbo_size = 0
        self.recovery_dtbo_offset = 0
        self.header_size = 0
        self.header_version = 0
    
    def parse(self, data):
        """Parse boot image header from bytes."""
        if len(data) < 1632:
            raise ValueError("Boot image header too small")
        
        magic = data[0:8]
        if magic != self.BOOT_MAGIC:
            raise ValueError(f"Invalid boot magic: {magic}")
        
        # Parse header fields for Android boot image header v0/v1/v2
        # Format: magic(8) + kernel_size(4) + kernel_addr(4) + ramdisk_size(4) + 
        #         ramdisk_addr(4) + second_size(4) + second_addr(4) + tags_addr(4) + 
        #         page_size(4) + header_version(4) + os_version(4) + name(16) + 
        #         cmdline(512) + id(32) + extra_cmdline(1024) + recovery_dtbo_size(4) + 
        #         recovery_dtbo_offset(8) + header_size(4)
        # Note: dt_size is in earlier versions at offset where header_version would be
        fmt = '<11I16s512s32s1024sIQI'
        fields = struct.unpack(fmt, data[8:1632])
        
        self.kernel_size = fields[0]
        self.kernel_addr = fields[1]
        self.ramdisk_size = fields[2]
        self.ramdisk_addr = fields[3]
        self.second_size = fields[4]
        self.second_addr = fields[5]
        self.tags_addr = fields[6]
        self.page_size = fields[7]
        # Field 8 can be dt_size (header v0) or header_version (header v1+)
        self.dt_size = fields[8]  # or header_version in v1+
        self.header_version = fields[8]  # Same field, different interpretation
        self.os_version = fields[9]
        self.name = fields[10]
        self.cmdline = fields[11]
        self.id = fields[12]
        self.extra_cmdline = fields[13]
        self.recovery_dtbo_size = fields[14]
        self.recovery_dtbo_offset = fields[15]
        self.header_size = fields[16]
        
        return self


def align_size(size, page_size):
    """Align size to page boundary."""
    return ((size + page_size - 1) // page_size) * page_size


def unpack_bootimg(boot_img_path, output_dir):
    """Unpack boot image to output directory."""
    
    if not os.path.exists(boot_img_path):
        print(f"Error: Boot image not found: {boot_img_path}")
        return False
    
    os.makedirs(output_dir, exist_ok=True)
    
    with open(boot_img_path, 'rb') as f:
        boot_data = f.read()
    
    # Parse header
    header = BootImageHeader()
    try:
        header.parse(boot_data)
    except ValueError as e:
        print(f"Error parsing boot image: {e}")
        return False
    
    print(f"Boot image header:")
    print(f"  Kernel size: {header.kernel_size}")
    print(f"  Ramdisk size: {header.ramdisk_size}")
    print(f"  Second size: {header.second_size}")
    print(f"  Page size: {header.page_size}")
    print(f"  Header version: {header.header_version}")
    print(f"  OS version: {header.os_version}")
    print(f"  Name: {header.name.rstrip(b'\\x00').decode('utf-8', errors='ignore')}")
    print(f"  Cmdline: {header.cmdline.rstrip(b'\\x00').decode('utf-8', errors='ignore')}")
    
    # Calculate offsets
    page_size = header.page_size
    kernel_offset = page_size
    ramdisk_offset = kernel_offset + align_size(header.kernel_size, page_size)
    second_offset = ramdisk_offset + align_size(header.ramdisk_size, page_size)
    dt_offset = second_offset + align_size(header.second_size, page_size)
    
    # Extract kernel
    if header.kernel_size > 0:
        kernel_path = os.path.join(output_dir, 'kernel')
        kernel_data = boot_data[kernel_offset:kernel_offset + header.kernel_size]
        with open(kernel_path, 'wb') as f:
            f.write(kernel_data)
        print(f"Extracted kernel to {kernel_path}")
    
    # Extract ramdisk
    if header.ramdisk_size > 0:
        ramdisk_path = os.path.join(output_dir, 'ramdisk.gz')
        ramdisk_data = boot_data[ramdisk_offset:ramdisk_offset + header.ramdisk_size]
        with open(ramdisk_path, 'wb') as f:
            f.write(ramdisk_data)
        print(f"Extracted ramdisk to {ramdisk_path}")
    
    # Extract second stage (if present)
    if header.second_size > 0:
        second_path = os.path.join(output_dir, 'second')
        second_data = boot_data[second_offset:second_offset + header.second_size]
        with open(second_path, 'wb') as f:
            f.write(second_data)
        print(f"Extracted second stage to {second_path}")
    
    # Extract device tree (if present)
    if header.dt_size > 0 and dt_offset + header.dt_size <= len(boot_data):
        dt_path = os.path.join(output_dir, 'dt.img')
        dt_data = boot_data[dt_offset:dt_offset + header.dt_size]
        with open(dt_path, 'wb') as f:
            f.write(dt_data)
        print(f"Extracted device tree to {dt_path}")
    
    # Save boot image info
    info_path = os.path.join(output_dir, 'bootimg.info')
    with open(info_path, 'w') as f:
        f.write(f"kernel_size={header.kernel_size}\n")
        f.write(f"kernel_addr=0x{header.kernel_addr:08x}\n")
        f.write(f"ramdisk_size={header.ramdisk_size}\n")
        f.write(f"ramdisk_addr=0x{header.ramdisk_addr:08x}\n")
        f.write(f"second_size={header.second_size}\n")
        f.write(f"second_addr=0x{header.second_addr:08x}\n")
        f.write(f"tags_addr=0x{header.tags_addr:08x}\n")
        f.write(f"page_size={header.page_size}\n")
        f.write(f"dt_size={header.dt_size}\n")
        f.write(f"header_version={header.header_version}\n")
        f.write(f"os_version={header.os_version}\n")
        f.write(f"name={header.name.rstrip(b'\\x00').decode('utf-8', errors='ignore')}\n")
        f.write(f"cmdline={header.cmdline.rstrip(b'\\x00').decode('utf-8', errors='ignore')}\n")
        f.write(f"extra_cmdline={header.extra_cmdline.rstrip(b'\\x00').decode('utf-8', errors='ignore')}\n")
    print(f"Saved boot image info to {info_path}")
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Unpack Android boot image')
    parser.add_argument('--input', '-i', required=True, help='Input boot.img file')
    parser.add_argument('--outdir', '-o', required=True, help='Output directory')
    
    args = parser.parse_args()
    
    success = unpack_bootimg(args.input, args.outdir)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
