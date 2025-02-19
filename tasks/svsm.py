from invoke import task
from os.path import basename, exists, join
from subprocess import run
from tasks.util.docker import copy_from_ctr_image
from tasks.util.env import GHCR_URL, GITHUB_ORG, PROJ_ROOT, SC2_ROOT
from tasks.util.kata import prepare_rootfs
from tasks.util.versions import IGVM_VERSION

SVSM_IMAGE_TAG = join(GHCR_URL, GITHUB_ORG, "svsm:main")
SVSM_KERNEL_IMAGE_TAG = join(GHCR_URL, GITHUB_ORG, "linux:svsm")
SVSM_QEMU_IMAGE_TAG = join(GHCR_URL, GITHUB_ORG, "qemu:svsm")

SVSM_ROOT = join(SC2_ROOT, "svsm")
SVSM_QEMU_DATA_DIR = join(SVSM_ROOT, "share", "qemu")

SVSM_GUEST_IMAGE = join(SVSM_QEMU_DATA_DIR, "sc2.qcow2")
# Can we do with less?
SVSM_GUEST_IMAGE_SIZE = "10G"


def get_kernel_version_from_ctr_image():
    tmp_file = "/tmp/sc2_kernel_release"
    copy_from_ctr_image(
        SVSM_KERNEL_IMAGE_TAG,
        ["/git/coconut-svsm/linux/include/config/kernel.release"],
        [tmp_file],
    )
    with open(tmp_file, "r") as fh:
        kernel_version = fh.read().strip()
    kernel_version_trimmed = (
        kernel_version if not kernel_version.endswith("+") else kernel_version[:-1]
    )

    return kernel_version, kernel_version_trimmed


@task
def build_guest_image(ctx, clean=False):
    """
    This function generates a qcow2 guest image with the SVSM-enlightened
    guest kernel.

    TODO: check if we really need a qcow image or we can get away with an
    initrd.
    """
    if clean and exists(SVSM_GUEST_IMAGE):
        run(f"sudo rm -f {SVSM_GUEST_IMAGE}", shell=True, check=True)

    # Get the kernel version we will install in the guest image
    kernel_version, kernel_version_trimmed = get_kernel_version_from_ctr_image()

    # Prepare our rootfs with the kata agent and co.
    rootfs_base_dir = "/tmp/svsm_rootfs_base_dir"
    # TODO: move hot_replace to False when done experimenting
    prepare_rootfs(rootfs_base_dir, debug=False, sc2=True, hot_replace=True)
    rootfs_dir = join(rootfs_base_dir, "rootfs")

    # Install deps
    result = run(
        "sudo DEBIAN_FRONTEND=noninteractive apt install -y qemu-utils",
        shell=True,
        capture_output=True,
    )
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())

    # Create qcow image
    result = run(
        f"sudo qemu-img create -f qcow2 -o preallocation=metadata {SVSM_GUEST_IMAGE} "
        f"{SVSM_GUEST_IMAGE_SIZE}",
        shell=True,
        capture_output=True,
    )
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())

    # Attach a loop device to the qcow image
    loop_device_file = "/tmp/svsm_loop_device"
    run(
        f"sudo losetup --find --show {SVSM_GUEST_IMAGE} > {loop_device_file}",
        shell=True,
        check=True,
    )
    with open(loop_device_file, "r") as fh:
        loop_device = fh.read().strip()

    # Create a partition in the image
    run(f"sudo parted -s {loop_device} mklabel msdos", shell=True, check=True)
    run(
        f"sudo parted -s {loop_device} mkpart primary ext4 1MiB 100%",
        shell=True,
        check=True,
    )

    # Detach and reattach loop device to pick up new partition
    run(f"sudo losetup -d {loop_device}", shell=True, check=True)
    run(
        f"sudo losetup --find --show -P {SVSM_GUEST_IMAGE} > {loop_device_file}",
        shell=True,
        check=True,
    )
    with open(loop_device_file, "r") as fh:
        loop_device = fh.read().strip()
    loop_device_part = loop_device + "p1"

    # Format partition as ext4 filesystem
    result = run(f"sudo mkfs.ext4 {loop_device_part}", shell=True, capture_output=True)
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())

    # Create mount dir
    mount_dir = "/tmp/svsm_guest_image"
    if exists(mount_dir):
        run(f"sudo rm -rf {mount_dir}", shell=True, check=True)
    run(f"sudo mkdir -p {mount_dir}", shell=True, check=True)

    # Mount loop device partition to mount dir
    result = run(
        f"sudo mount {loop_device_part} {mount_dir}",
        shell=True,
        capture_output=True,
    )
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())

    def cleanup_loop_device():
        run(f"sudo umount {mount_dir}", shell=True, check=True)
        run(f"sudo losetup -d {loop_device}", shell=True, check=True)

    # Copy our rootfs into the qcow image
    result = run(f"sudo cp -a {rootfs_dir}/* {mount_dir}", shell=True, check=True)

    # Install the SVSM guest kernel into the image
    run(f"sudo mkdir -p {mount_dir}/boot", shell=True, check=True)
    ctr_paths = [
        "/git/coconut-svsm/linux/arch/x86/boot/bzImage",
        f"/opt/sc2/svsm/share/linux/modules/lib/modules/{kernel_version}",
        "/git/coconut-svsm/linux/.config",
    ]
    host_paths = [
        f"{mount_dir}/boot/vmlinuz-{kernel_version_trimmed}",
        f"{mount_dir}/lib/modules/{kernel_version_trimmed}",
        f"{mount_dir}/boot/config-{kernel_version_trimmed}",
    ]
    copy_from_ctr_image(
        SVSM_KERNEL_IMAGE_TAG, ctr_paths, host_paths, requires_sudo=True
    )

    # Configure GRUB inside the guest image
    subsystems = ["dev", "proc", "sys"]

    def unmount_subsys():
        for subsystem in subsystems:
            run(f"sudo umount {mount_dir}/{subsystem}", shell=True, check=True)

    for subsystem in subsystems:
        result = run(
            f"sudo mount --bind /{subsystem} {mount_dir}/{subsystem}",
            shell=True,
            capture_output=True,
        )

        if result.returncode != 0:
            print(result.stderr.decode("utf-8").strip())
            cleanup_loop_device()
            raise RuntimeError("Error mounting /proc and /sys")

    run(f"sudo mkdir -p {mount_dir}/usr/share/locale", shell=True, check=True)
    # Make sure to soft-link /bin/sh to the right binary, as it is used
    #  by update-grub
    cmd = """
sudo chroot {mount_dir} /usr/bin/sh <<EOF
ln -s /usr/bin/dash /bin/sh
grub-install --target=i386-pc {loop_device}
update-grub
EOF
""".format(
        mount_dir=mount_dir, loop_device=loop_device
    )
    result = run(cmd, shell=True, capture_output=True)
    if result.returncode != 0:
        print(result.stderr.decode("utf-8").strip())
        unmount_subsys()
        raise RuntimeError("Error configuring GRUB in guest")

    # Set the kernel as our default
    cmd = """
sudo chroot {mount_dir} /usr/bin/sh <<EOF
# TODO: `mkinitramfs` seem to not be working (do we need it at all?)
mkinitramfs -o /boot/initrd.img-{kernel_version} {kernel_version} 2> /tmp/mk_log
echo "GRUB_DEFAULT='Advanced options for Ubuntu>vmlinuz-{kernel_version}'" \
        >> /etc/default/grub
update-grub
EOF
""".format(
        mount_dir=mount_dir, kernel_version=kernel_version_trimmed
    )
    result = run(cmd, shell=True, capture_output=True)
    if result.returncode != 0:
        print(result.stderr.decode("utf-8").strip())
        unmount_subsys()
        cleanup_loop_device()
        raise RuntimeError("Error setting default kernel")

    # Clean-up
    unmount_subsys()
    cleanup_loop_device()


def do_build_kernel(nocache=False):
    # First, generate the right config file: we start from our current one,
    # and make sure the following are set:
    # - CONFIG_KVM_AMD_SEV: for general SNP support in KVM
    # - CONFIG_TCG_PLATFORM: for vTPM support in the SVSM

    # TODO: move to tasks/util/kernel.py
    # Use a tmp file to not rely on being able to capture our stdout
    tmp_file = "/tmp/svsm_kernel_config"
    run(f"uname -r > {tmp_file}", shell=True, check=True)
    with open(tmp_file, "r") as fh:
        current_kernel_name = fh.read().strip()

    run(f"cp /boot/config-{current_kernel_name} {tmp_file}", shell=True, check=True)
    with open(tmp_file, "r") as fh:
        kernel_config = fh.read().strip().split("\n")

    snp_set = False
    tpm_set = False
    for line in kernel_config:
        if line.startswith("CONFIG_KVM_AMD_SEV="):
            line = "CONFIG_KVM_AMD_SEV=y"
            snp_set = True

        if line.startswith("CONFIG_TCG_PLATFORM="):
            line = "CONFIG_TCG_PLATFORM=y"
            tpm_set = True

    # Cover for the case where the entries are not there at all
    if not snp_set:
        kernel_config += ["CONFIG_KVM_AMD_SEV=y"]
    if not tpm_set:
        kernel_config += ["CONFIG_TCG_PLATFORM=y"]

    with open(tmp_file, "w") as fh:
        fh.write("\n".join(kernel_config) + "\n")

    build_args = {
        "KERNEL_CONFIG_FILE": basename(tmp_file),
        "MODULES_OUTDIR": join(SVSM_ROOT, "share", "linux", "modules"),
    }
    build_args_str = [
        "--build-arg {}={}".format(key, build_args[key]) for key in build_args
    ]
    build_args_str = " ".join(build_args_str)

    docker_cmd = "docker build{} {} -t {} -f {} /tmp".format(
        " --no-cache" if nocache else "",
        build_args_str,
        # f"{tmp_file}:/tmp/kernel_config",
        SVSM_KERNEL_IMAGE_TAG,
        join(PROJ_ROOT, "docker", "svsm_kernel.dockerfile"),
    )
    run(docker_cmd, shell=True, check=True, cwd=PROJ_ROOT)


@task
def build_kernel(ctx, nocache=False, push=False):
    """
    Build the host/guest kernel fork to use with the SVSM
    """
    do_build_kernel(nocache=nocache)


def do_build_qemu(nocache=False):
    build_args = {
        "IGVM_VERSION": IGVM_VERSION,
        "QEMU_DATADIR": SVSM_QEMU_DATA_DIR,
        "QEMU_PREFIX": SVSM_ROOT,
    }
    build_args_str = [
        "--build-arg {}={}".format(key, build_args[key]) for key in build_args
    ]
    build_args_str = " ".join(build_args_str)

    docker_cmd = "docker build{} {} -t {} -f {} .".format(
        " --no-cache" if nocache else "",
        build_args_str,
        SVSM_QEMU_IMAGE_TAG,
        join(PROJ_ROOT, "docker", "svsm_qemu.dockerfile"),
    )
    run(docker_cmd, shell=True, check=True, cwd=PROJ_ROOT)


@task
def do_build_svsm(ctx, nocache=False):
    build_args = {
        "OVMF_FILE": "OVMF.fd",
    }
    build_args_str = [
        "--build-arg {}={}".format(key, build_args[key]) for key in build_args
    ]
    build_args_str = " ".join(build_args_str)

    docker_cmd = "docker build{} {} -t {} -f {} {}".format(
        " --no-cache" if nocache else "",
        build_args_str,
        SVSM_IMAGE_TAG,
        join(PROJ_ROOT, "docker", "svsm.dockerfile"),
        join(SVSM_ROOT, "share", "ovmf"),
    )
    run(docker_cmd, shell=True, check=True, cwd=PROJ_ROOT)


@task
def build_qemu(ctx, nocache=False, push=False):
    """
    Build the QEMU fork for its use with the SVSM
    """
    do_build_qemu(nocache=nocache)

    if push:
        run(f"docker push {SVSM_QEMU_IMAGE_TAG}", shell=True, check=True)


def install(debug, clean):
    if clean and exists(SVSM_ROOT):
        result = run(f"sudo rm -rf {SVSM_ROOT}", shell=True, capture_output=True)
        assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())

    run(f"sudo mkdir -p ${SVSM_ROOT}", shell=True, check=True)

    # TODO: install guest qcow2 image

    # Install QEMU and OVMF
    ctr_paths = [
        join(SVSM_ROOT, "bin", "qemu-system-x86_64"),
        join(SVSM_ROOT, "share", "qemu", "qemu/"),
        "/git/coconut-svsm/edk2/Build/OvmfX64/RELEASE_GCC5/FV/OVMF.fd",
    ]
    host_paths = [
        join(SVSM_ROOT, "bin", "qemu-system-x86_64"),
        join(SVSM_ROOT, "share", "qemu"),
        join(SVSM_ROOT, "share", "ovmf", "OVMF.fd"),
    ]
    copy_from_ctr_image(SVSM_QEMU_IMAGE_TAG, ctr_paths, host_paths, requires_sudo=True)


@task
def foo(ctx):
    install(debug=False, clean=False)


@task
def install_host_kernel(ctx):
    """
    Install the SVSM kernel in the host system
    """
    kernel_version, kernel_version_trimmed = get_kernel_version_from_ctr_image()

    # Install the SVSM guest kernel into the host
    ctr_paths = [
        "/git/coconut-svsm/linux/arch/x86/boot/bzImage",
        f"/opt/sc2/svsm/share/linux/modules/lib/modules/{kernel_version}",
        "/git/coconut-svsm/linux/.config",
    ]
    host_paths = [
        f"/boot/vmlinuz-{kernel_version_trimmed}",
        f"/lib/modules/{kernel_version_trimmed}",
        f"/boot/config-{kernel_version_trimmed}",
    ]
    copy_from_ctr_image(
        SVSM_KERNEL_IMAGE_TAG, ctr_paths, host_paths, requires_sudo=True
    )

    # Generate the corresponding kernel image
    result = run(
        f"sudo mkinitramfs -o /boot/initrd.img-{kernel_version_trimmed} "
        f"{kernel_version_trimmed}",
        shell=True,
        capture_output=True,
    )
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())

    # Replace the GRUB_DEFAULT value
    grub_default = (
        "Advanced options for Ubuntu>Ubuntu, with Linux " f"{kernel_version_trimmed}"
    )
    result = run(
        f"sudo sed -i 's/^GRUB_DEFAULT=.*/GRUB_DEFAULT=\"{grub_default}\"/' "
        "/etc/default/grub",
        shell=True,
        capture_output=True,
    )
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
