#!/bin/bash

SVSM_ROOT=/opt/sc2/svsm

# C-bit pos may be obtained by running coconut-svsm/svsm/utils/cbit
CBIT_POS=51

IGVM=${SVSM_ROOT}/share/igvm/coconut-qemu.igvm
KERNEL=${SVSM_ROOT}/share/sc2/vmlinuz-kata-containers-sc2
INITRD=/opt/sc2/svsm/share/sc2/initrd-kata.img

# Ensure terminal settings are restored on exit
orig_stty=$(stty -g)
trap "stty '$orig_stty'" EXIT

# Remap Ctrl-C to Ctrl-] to allow the guest to handle Ctrl-C.
stty intr ^]

sudo ${SVSM_ROOT}/bin/qemu-system-x86_64 \
    -cpu EPYC-v4 \
    -machine q35,confidential-guest-support=sev0,memory-backend=ram1,igvm-cfg=igvm0,accel=kvm \
    -object memory-backend-memfd,id=ram1,size=8G,share=true,prealloc=false,reserve=false \
    -object sev-snp-guest,id=sev0,cbitpos=${CBIT_POS},reduced-phys-bits=1 \
    -object igvm-cfg,id=igvm0,file=$IGVM \
    -smp 8 \
    -no-reboot \
    -netdev user,id=vmnic -device e1000,netdev=vmnic,romfile= \
    -kernel ${KERNEL} \
    -initrd ${INITRD} \
    -append "console=ttyS0 loglevel=8 earlyprintk=serial rdinit=/bin/sh" \
    -monitor none \
    -nographic \
    -serial stdio \
    -serial pty
