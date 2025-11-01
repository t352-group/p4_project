#!/usr/bin/env python3
import argparse
import os
import shutil
import struct
import subprocess
import sys
import tempfile

ANDROID_MAGIC = b'ANDROID!'

def try_abootimg_extract(input_img: str, output_dir: str) -> bool:
    # abootimg -x writes bootimg.cfg, zImage, initrd.img into CWD
    with tempfile.TemporaryDirectory() as tmp:
        try:
            subprocess.run(['abootimg', '-x', input_img],
                           cwd=tmp, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

        # Map outputs to our expected names
        kernel_candidates = ['zImage', 'kernel', 'zImage-dtb', 'Image.gz-dtb', 'Image.lz4-dtb', 'Image']
        ramdisk_candidates = ['initrd.img', 'ramdisk.img', 'ramdisk.gz', 'ramdisk.cpio.gz', 'initramfs.cpio.gz']

        kernel_src = next((os.path.join(tmp, f) for f in kernel_candidates if os.path.exists(os.path.join(tmp, f))), None)
        ramdisk_src = next((os.path.join(tmp, f) for f in ramdisk_candidates if os.path.exists(os.path.join(tmp, f))), None)
        cfg_src = os.path.join(tmp, 'bootimg.cfg') if os.path.exists(os.path.join(tmp, 'bootimg.cfg')) else None

        if not kernel_src or not ramdisk_src:
            return False

        os.makedirs(output_dir, exist_ok=True)
        shutil.copyfile(kernel_src, os.path.join(output_dir, 'kernel'))
        shutil.copyfile(ramdisk_src, os.path.join(output_dir, 'ramdisk.img'))
        if cfg_src:
            shutil.copyfile(cfg_src, os.path.join(output_dir, 'bootimg.cfg'))

        # Best-effort bootimg.info from cfg
        if cfg_src:
            info_path = os.path.join(output_dir, 'bootimg.info')
            with open(cfg_src, 'r') as f, open(info_path, 'w') as out:
                cfg = f.read()
                def val(key, default='0'):
                    import re
                    m = re.search(r'^%s\\s*=\\s*(\\S+)' % key, cfg, flags=re.M)
                    return m.group(1) if m else default
                out.write(f"kernel_size=0\n")  # unknown from cfg
                out.write(f"kernel_addr={val('kerneladdr','0')}\n")
                out.write(f"ramdisk_size=0\n")
                out.write(f"ramdisk_addr={val('ramdiskaddr','0')}\n")
                out.write(f"second_size=0\n")
                out.write(f"second_addr=0\n")
                out.write(f"tags_addr={val('tagsaddr','0')}\n")
                out.write(f"page_size={val('pagesize','2048')}\n")
                out.write(f"dt_size=0\n")
                out.write(f"header_version=0\n")
                out.write(f"os_version=0\n")
                out.write(f"name=\n")
                out.write(f"cmdline=\n")
                out.write(f"extra_cmdline=\n")

        print("Unpacked with abootimg")
        return True

def align_up(x, page_size):
    return (x + page_size - 1) // page_size * page_size

def try_minimal_parse(input_img: str, output_dir: str) -> bool:
    # Minimal parser for legacy headers v0/v1 (best effort)
    with open(input_img, 'rb') as f:
        data = f.read()

    if not data.startswith(ANDROID_MAGIC):
        print(f"Error parsing boot image: Invalid boot magic: {data[:8]!r}", file=sys.stderr)
        return False

    # Legacy header (v0/v1)
    # struct boot_img_hdr {
    #   char magic[8];
    #   uint32 kernel_size; 4
    #   uint32 kernel_addr; 8
    #   uint32 ramdisk_size; 12
    #   uint32 ramdisk_addr; 16
    #   uint32 second_size; 20
    #   uint32 second_addr; 24
    #   uint32 tags_addr; 28
    #   uint32 page_size; 32
    #   uint32 dt_size; 36
    #   uint32 os_version; 40 (v1); treat as present
    #   char name[16]; 56
    #   char cmdline[512]; 568
    #   uint32 id[8]; 600
    # };
    try:
        hdr = struct.unpack_from('<8s10I16s512s8I', data, 0)
    except struct.error:
        print("Error parsing boot image: header too short or unsupported format", file=sys.stderr)
        return False

    magic = hdr[0]
    kernel_size = hdr[1]
    ramdisk_size = hdr[3]
    second_size = hdr[5]
    page_size = hdr[8]
    dt_size = hdr[9]
    os_version = hdr[10]
    name = hdr[11].split(b'\x00', 1)[0].decode(errors='ignore')
    cmdline = hdr[12].split(b'\x00', 1)[0].decode(errors='ignore')

    if page_size == 0:
        page_size = 2048

    off = page_size
    kernel_off = off
    ramdisk_off = align_up(kernel_off + kernel_size, page_size)
    second_off = align_up(ramdisk_off + ramdisk_size, page_size)
    dt_off = align_up(second_off + second_size, page_size)

    os.makedirs(output_dir, exist_ok=True)
    if kernel_size > 0:
        with open(os.path.join(output_dir, 'kernel'), 'wb') as kf:
            kf.write(data[kernel_off:kernel_off + kernel_size])

    if ramdisk_size > 0:
        with open(os.path.join(output_dir, 'ramdisk.img'), 'wb') as rf:
            rf.write(data[ramdisk_off:ramdisk_off + ramdisk_size])

    if second_size > 0:
        with open(os.path.join(output_dir, 'second'), 'wb') as sf:
            sf.write(data[second_off:second_off + second_size])

    if dt_size > 0 and dt_off + dt_size <= len(data):
        with open(os.path.join(output_dir, 'dt.img'), 'wb') as df:
            df.write(data[dt_off:dt_off + dt_size])

    with open(os.path.join(output_dir, 'bootimg.info'), 'w') as inf:
        inf.write(f"kernel_size={kernel_size}\n")
        inf.write(f"kernel_addr=0x0\n")
        inf.write(f"ramdisk_size={ramdisk_size}\n")
        inf.write(f"ramdisk_addr=0x0\n")
        inf.write(f"second_size={second_size}\n")
        inf.write(f"second_addr=0x0\n")
        inf.write(f"tags_addr=0x0\n")
        inf.write(f"page_size={page_size}\n")
        inf.write(f"dt_size={dt_size}\n")
        inf.write(f"header_version=0\n")
        inf.write(f"os_version={os_version}\n")
        inf.write(f"name={name}\n")
        inf.write(f"cmdline={cmdline}\n")
        inf.write(f"extra_cmdline=\n")

    print("Unpacked with minimal legacy parser")
    return True

def main():
    ap = argparse.ArgumentParser(description='Unpack Android boot image (abootimg/legacy best-effort)')
    ap.add_argument('--input', '-i', required=True, help='Input boot.img file')
    ap.add_argument('--outdir', '-o', required=True, help='Output directory')
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # Prefer abootimg if it can handle this image
    if try_abootimg_extract(args.input, args.outdir):
        sys.exit(0)

    # Fallback: minimal parser for older headers
    ok = try_minimal_parse(args.input, args.outdir)
    sys.exit(0 if ok else 1)

if __name__ == '__main__':
    main()
