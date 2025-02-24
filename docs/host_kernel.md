# Host Kernel Set-Up

Some of the SC2 features require specific host-kernel patches. You can see
the expected host-kernel versions in [`./tasks/util/versions.py`](
./tasks/util/versions.py), which we also summarise in the following table.

| **SEV-SNP** | **TDX** |
|---|---|
| `6.11.0-snp-host-cc2568386` | `6.8.0-1004-intel` |

## SNP

For SNP hosts, we need kernel patches to (i) enable SNP, and (ii) enable the
SVSM. The former were upstreamed in `6.11`, but we still need the latter. To
build the host-kernel from source you may use:

```bash
git clone -b svsm --depth=1 https://github.com/coconut-svsm/linux ../svsm-linux
```

and then just run:

```bash
cd ../svsm-linux
cp /boot/config-$(uname -r) .config
# Make sure CONFIG_KVM_AMD_SEV=y and CONFIG_TCG_PLATFORM=y
make olddefconfig
make -j $(nproc)

sudo make modules_install
sudo make install
```

Lastly, update the `GRUB_DEFAULT` variable in `/etc/default/grub` to:

```
GRUB_DEFAULT="Advanced options for Ubuntu>Ubuntu, with Linux 6.11.0-......"
sudo update-grub
sudo reboot now
```

which you can copy and paste from `ls -lart /boot`.
