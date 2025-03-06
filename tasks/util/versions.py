# CoCo versions (note that the CoCo release pins the Kata Version)
COCO_VERSION = "0.12.0"
KATA_VERSION = "3.14.0"

# Base software versions
GO_VERSION = "1.23.0"
RUST_VERSION = "1.80.0"

# Kubernetes versions
CONTAINERD_VERSION = "1.7.19"
K8S_VERSION = "1.32.1"
CALICO_VERSION = "3.28.1"
CNI_VERSION = "1.3.0"
CRICTL_VERSION = "1.32.0"
K9S_VERSION = "0.32.5"
PAUSE_IMAGE_VERSION = "3.9"

# Container image managament versions
REGISTRY_VERSION = "2.8"
COSIGN_VERSION = "2.2.0"
SKOPEO_VERSION = "1.13.0"

# Nydus versions
NYDUS_VERSION = "2.3.0"
NYDUS_SNAPSHOTTER_VERSION = "0.15.0"

# Knative versions
KNATIVE_VERSION = "1.15.0"

# Kernel versions
# WARNING: if we update the host kernel version, make sure to update it in the
# table in ./docs/host_kernel.md
HOST_KERNEL_VERSION_SNP = "6.11.0-snp-host-cc2568386"
HOST_KERNEL_VERSION_TDX = "6.8.0-1013-intel"
GUEST_KERNEL_VERSION = "6.12.8"

# Coconut SVSM versions
IGVM_VERSION = "0.3.4"

# Firmware
OVMF_VERSION = "edk2-stable202411"
