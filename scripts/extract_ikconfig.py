#!/usr/bin/env python3
import sys
import gzip
import io

def try_extract_from_bytes(data: bytes) -> str:
    # Search for gzip members and try to decompress; return first that looks like a config
    gz_magic = b'\x1f\x8b\x08'
    idx = 0
    while True:
        i = data.find(gz_magic, idx)
        if i < 0:
            break
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(data[i:])) as gf:
                content = gf.read().decode('utf-8', errors='ignore')
                if 'CONFIG_' in content:
                    return content
        except Exception:
            pass
        idx = i + 1
    return ""

def main():
    if len(sys.argv) < 2:
        print("Usage: extract_ikconfig.py <kernel_or_blob> [more files...]", file=sys.stderr)
        sys.exit(1)

    for path in sys.argv[1:]:
        try:
            with open(path, 'rb') as f:
                data = f.read()
            cfg = try_extract_from_bytes(data)
            if cfg:
                print(cfg)
                return
        except Exception:
            continue

    # If nothing found, exit 0 with empty output so caller can fallback
    sys.exit(0)

if __name__ == '__main__':
    main()