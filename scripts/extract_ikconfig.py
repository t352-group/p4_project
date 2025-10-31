#!/usr/bin/env python3
"""
Extract kernel configuration from a kernel image.
This script searches for the compressed kernel config embedded in the kernel image.
"""

import argparse
import gzip
import os
import sys
import zlib


# Magic strings that mark the beginning and end of embedded kernel config
CONFIG_START = b'IKCFG_ST'
CONFIG_END = b'IKCFG_ED'


def find_config_in_data(data):
    """
    Search for embedded kernel config in binary data.
    The config is stored between CONFIG_START and CONFIG_END markers,
    and is compressed with gzip.
    """
    # Find start marker
    start_idx = data.find(CONFIG_START)
    if start_idx == -1:
        return None
    
    # Find end marker
    end_idx = data.find(CONFIG_END, start_idx)
    if end_idx == -1:
        return None
    
    # Extract compressed config data (skip the start marker)
    compressed_start = start_idx + len(CONFIG_START)
    compressed_data = data[compressed_start:end_idx]
    
    if not compressed_data:
        return None
    
    # Try to decompress
    try:
        config_data = gzip.decompress(compressed_data)
        return config_data.decode('utf-8', errors='ignore')
    except Exception:
        # Try zlib decompression as fallback
        try:
            config_data = zlib.decompress(compressed_data)
            return config_data.decode('utf-8', errors='ignore')
        except Exception:
            return None


def extract_config_from_file(kernel_path):
    """Extract kernel config from a kernel image file."""
    
    if not os.path.exists(kernel_path):
        print(f"Error: File not found: {kernel_path}", file=sys.stderr)
        return None
    
    try:
        with open(kernel_path, 'rb') as f:
            data = f.read()
    except Exception as e:
        print(f"Error reading file {kernel_path}: {e}", file=sys.stderr)
        return None
    
    config = find_config_in_data(data)
    return config


def extract_from_directory(dir_path):
    """Try to extract config from all files in a directory."""
    
    if not os.path.isdir(dir_path):
        return extract_config_from_file(dir_path)
    
    # Common kernel image names
    kernel_names = ['kernel', 'Image', 'Image.gz', 'zImage', 'vmlinux', 'vmlinuz']
    
    # Try each known kernel name
    for name in kernel_names:
        kernel_path = os.path.join(dir_path, name)
        if os.path.exists(kernel_path):
            config = extract_config_from_file(kernel_path)
            if config:
                return config
    
    # Try all files in directory
    try:
        for filename in os.listdir(dir_path):
            filepath = os.path.join(dir_path, filename)
            if os.path.isfile(filepath):
                config = extract_config_from_file(filepath)
                if config:
                    return config
    except Exception as e:
        print(f"Error scanning directory {dir_path}: {e}", file=sys.stderr)
    
    return None


def main():
    parser = argparse.ArgumentParser(
        description='Extract kernel configuration from kernel image',
        epilog='Can process a single kernel file or search a directory for kernel images.'
    )
    parser.add_argument('path', nargs='+', help='Kernel file path or directory to search')
    parser.add_argument('-o', '--output', help='Output file (default: stdout)')
    
    args = parser.parse_args()
    
    config = None
    
    # Try each path provided
    for path in args.path:
        if os.path.isdir(path):
            config = extract_from_directory(path)
        else:
            config = extract_config_from_file(path)
        
        if config:
            break
    
    if not config:
        print("Error: Could not find kernel config in any of the provided files/directories", file=sys.stderr)
        print("The kernel may not have been compiled with CONFIG_IKCONFIG enabled", file=sys.stderr)
        sys.exit(1)
    
    # Output the config
    if args.output:
        try:
            with open(args.output, 'w') as f:
                f.write(config)
            print(f"Kernel config extracted to {args.output}", file=sys.stderr)
        except Exception as e:
            print(f"Error writing to {args.output}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(config)
    
    sys.exit(0)


if __name__ == '__main__':
    main()
