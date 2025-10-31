# KernelSU-next + SUSFS Patch for Pixel 4 (Android 13)

This repository contains a GitHub Actions workflow and helper scripts to build a KernelSU-next + SUSFS patched kernel for Google Pixel 4 on Android 13.

## Overview

The workflow automates the process of:
1. Downloading or using a stock boot image
2. Unpacking the boot image to extract kernel and ramdisk
3. Checking out the kernel source (from 0xSoul24/kernel_google_msm-4.14)
4. Applying KernelSU-next patches (from tiann/KernelSU)
5. Applying SUSFS patches (from sidex15/susfs4ksu-module)
6. Building the patched kernel with Android NDK
7. Repacking the boot image with the patched kernel
8. Providing `boot_patched.img` as a downloadable artifact

## Prerequisites

### Repository Secrets

You need to create a repository secret named `BOOT_IMG_URL` containing the URL to download your Pixel 4 stock boot image.

**To add the secret:**
1. Go to your repository settings
2. Navigate to "Secrets and variables" → "Actions"
3. Click "New repository secret"
4. Name: `BOOT_IMG_URL`
5. Value: Your boot image URL (e.g., `https://your-storage.com/boot.img`)

## Usage

### Running the Workflow

1. Go to the "Actions" tab in your repository
2. Select the "build-kernelsu-next-susfs" workflow
3. Click "Run workflow"
4. Choose whether to use the boot image URL from secrets (default: true)
5. Click "Run workflow" to start the build

### Workflow Inputs

- **use_boot_url** (default: `true`): 
  - `true`: Download boot.img from the URL specified in the `BOOT_IMG_URL` secret
  - `false`: Use a boot.img file from the repository root (if present)

### Build Output

After the workflow completes successfully, you can download the `boot_patched.img` artifact from the workflow run page.

## Files in This Repository

### Helper Scripts

- **`scripts/unpack_bootimg.py`**: Unpacks Android boot images into components
  - Extracts: kernel, ramdisk, second stage, device tree
  - Creates bootimg.info with image parameters
  
- **`scripts/extract_ikconfig.py`**: Extracts embedded kernel configuration
  - Searches for IKCONFIG markers in kernel images
  - Decompresses gzip-compressed config data
  
- **`scripts/repack_boot.sh`**: Repacks boot images with new kernel
  - Supports mkbootimg, abootimg, and Python fallback
  - Preserves original boot image parameters

### Workflow

- **`.github/workflows/main.yml`**: GitHub Actions workflow
  - Defines the complete build pipeline
  - Handles kernel source checkout
  - Applies patches and builds the kernel
  - Creates the final patched boot image

## Important Notes

### Kernel Source

The workflow uses the kernel source from `0xSoul24/kernel_google_msm-4.14`, which is the Google Pixel 4 kernel (msm-4.14 branch).

### Patches

- **KernelSU-next**: Cloned from [tiann/KernelSU](https://github.com/tiann/KernelSU)
- **SUSFS**: Cloned from [sidex15/susfs4ksu-module](https://github.com/sidex15/susfs4ksu-module)

The workflow looks for patch files in:
- `kernelsu-next/patches/*.patch`
- `susfs4ksu-module/susfs.patch` or `susfs4ksu-module/*.patch`

If patches don't apply cleanly, you may need to manually resolve conflicts or adapt the integration steps based on the documentation of these projects.

### Device Configuration

The workflow targets the Google Pixel 4 ("flame") with the following defconfigs:
- `flame_defconfig`
- `flame-perf_defconfig`

If your boot image contains an embedded kernel config (IKCONFIG), it will be extracted and used instead.

## Customization

### Using a Different Kernel Source

Edit `.github/workflows/main.yml` and change the `REPO` environment variable:

```yaml
env:
  REPO: your-username/your-kernel-repo
```

### Modifying Build Parameters

You can adjust the following in the workflow:
- **NDK Version**: Change `NDK_VERSION` environment variable
- **Build Configuration**: Modify the build step to use different defconfigs
- **Compiler Flags**: Add additional flags in the build step

### Adding Custom Patches

1. Add your patch files to the repository
2. Modify the "Apply KernelSU-next and susfs patches" step in the workflow
3. Add commands to apply your custom patches

## Troubleshooting

### Build Failures

If the build fails:
1. Check the GitHub Actions logs for error messages
2. Verify that the boot image URL is accessible
3. Ensure patches are compatible with the kernel version
4. Check that the defconfig exists in the kernel source

### Patch Application Failures

If patches don't apply:
1. Check the kernel source version compatibility
2. Look for `.rej` files to see which hunks failed
3. Manually apply patches or update them for the kernel version

### Boot Image Issues

If unpacking/repacking fails:
1. Verify the boot image format is Android boot image v0/v1/v2
2. Check that all required components are present
3. Ensure the boot image is for Pixel 4

## Security

This workflow:
- ✅ Uses official Android NDK for building
- ✅ Clones from well-known KernelSU and SUSFS repositories
- ✅ Passes CodeQL security scanning
- ✅ Does not expose secrets in logs

**Warning**: Only use boot images from trusted sources. Malicious boot images could compromise your device.

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test the workflow
5. Submit a pull request

## License

The scripts in this repository are provided as-is for educational purposes.

Please respect the licenses of:
- The kernel source (GPL v2)
- KernelSU (GPL v3)
- SUSFS (respective license)
- Android tools (Apache 2.0)

## Disclaimer

**Use at your own risk!** Modifying your device's boot image can:
- Void your warranty
- Brick your device if done incorrectly
- Cause data loss
- Lead to security vulnerabilities

Always backup your data and ensure you have a way to recover your device before flashing custom boot images.

## Support

For issues related to:
- **This workflow**: Open an issue in this repository
- **KernelSU**: Visit [tiann/KernelSU](https://github.com/tiann/KernelSU)
- **SUSFS**: Visit [sidex15/susfs4ksu-module](https://github.com/sidex15/susfs4ksu-module)
- **Kernel source**: Visit the respective kernel repository

## Acknowledgments

- [tiann](https://github.com/tiann) for KernelSU
- [sidex15](https://github.com/sidex15) for SUSFS
- [0xSoul24](https://github.com/0xSoul24) for the Pixel 4 kernel source
- The Android Open Source Project for tools and documentation
