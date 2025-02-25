# Coconut-SVSM

SC2 uses the [Coconut-SVSM](https://github.com/coconut-svsm/svsm) as an SVSM for
its confidential pods. The SVSM requires its own forked versions of the kernel,
QEMU, and OVMF.

> [!WARNING]
> Currently we only support running SNP guests in SVSM using a manual script
> with QEMU. In the future we will integrate it with Kata pods (#148).

## Quick Start

After installing SC2, you can run:

```bash
inv svsm.install [--clean]
```

and then:

```bash
./bin/launch_svsm.sh
```

to start an SNP guest in the SVSM.

## Guest Kernel

We have an automated script to build the guest kernel which, for some reason,
we still cannot use from the host (the `initramfs` seems to be corrupted, but
the kernel is fine to run in the guest).

You can trigger the build by running:

```bash
inv svsm.build-guest-kernel
```

## QEMU/OVMF

The SVSM uses the [IGVM](https://github.com/microsoft/igvm) image format to
package the initial guest image containing the virtual firmware (OVMF) as well
as the SVSM itself.

We need a patched version of QEMU and OVMF to support using IGVM files. You
can build both by running:

```bash
inv svsm.build-qemu
```
