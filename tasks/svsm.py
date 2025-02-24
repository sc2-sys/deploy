from invoke import task
from os.path import basename, exists, join
from subprocess import run
from tasks.util.docker import copy_from_ctr_image
from tasks.util.env import GHCR_URL, GITHUB_ORG, PROJ_ROOT, SC2_ROOT
from tasks.util.kata import KATA_AGENT_SOURCE_DIR, KATA_IMAGE_TAG, KATA_SOURCE_DIR
from tasks.util.kernel import get_host_kernel_version
from tasks.util.versions import IGVM_VERSION

SVSM_IMAGE_TAG = join(GHCR_URL, GITHUB_ORG, "svsm:main")
SVSM_KERNEL_IMAGE_TAG = join(GHCR_URL, GITHUB_ORG, "linux:svsm")
SVSM_QEMU_IMAGE_TAG = join(GHCR_URL, GITHUB_ORG, "qemu:svsm")

SVSM_ROOT = join(SC2_ROOT, "svsm")
SVSM_QEMU_DATA_DIR = join(SVSM_ROOT, "share")

SVSM_GUEST_INITRD = join(SVSM_ROOT, "share", "sc2", "initrd-kata.img")


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


def do_build_initrd(clean=False):
    if clean and exists(SVSM_GUEST_INITRD):
        run(f"sudo rm -f {SVSM_GUEST_INITRD}", shell=True, check=True)

    if exists(SVSM_GUEST_INITRD):
        return

    # TODO: this initrd is built using dracut, which is different to how we
    # normally build initrd's for SC2 in Kata. Whenever we incorportate the
    # SVSM into SC2, we will have to converge this method with the regular
    # initrd preparation for SC2.

    # Prepare our rootfs with the kata agent and co.
    initrd_base_dir = "/tmp/svsm_initrd_base_dir"
    run(f"sudo rm -rf {initrd_base_dir}", shell=True, check=True)
    run(f"sudo mkdir -p {initrd_base_dir}", shell=True, check=True)

    host_paths = [
        join(initrd_base_dir, "VERSION"),
        join(initrd_base_dir, "kata-agent"),
        join(initrd_base_dir, "tools", "osbuilder", "Makefile"),
        join(initrd_base_dir, "tools", "osbuilder", "dracut"),
        join(initrd_base_dir, "tools", "osbuilder", "initrd-builder"),
        join(initrd_base_dir, "tools", "osbuilder", "rootfs-builder"),
        join(initrd_base_dir, "tools", "osbuilder", "scripts"),
    ]
    ctr_paths = [
        f"{KATA_SOURCE_DIR}/VERSION",
        f"{KATA_AGENT_SOURCE_DIR}/target/x86_64-unknown-linux-musl/release/kata-agent",
        f"{KATA_SOURCE_DIR}/tools/osbuilder/Makefile",
        f"{KATA_SOURCE_DIR}/tools/osbuilder/dracut",
        f"{KATA_SOURCE_DIR}/tools/osbuilder/initrd-builder",
        f"{KATA_SOURCE_DIR}/tools/osbuilder/rootfs-builder",
        f"{KATA_SOURCE_DIR}/tools/osbuilder/scripts",
    ]
    copy_from_ctr_image(KATA_IMAGE_TAG, ctr_paths, host_paths, requires_sudo=True)

    # This initrd must contain our agent, but also the kernel modules
    # corresponding to an SVSM-enlightened kernel
    initrd_cmd = [
        "sudo -E make",
        "BUILD_METHOD=dracut",
        f"TARGET_INITRD={SVSM_GUEST_INITRD}",
        "AGENT_SOURCE_BIN={}".format(join(initrd_base_dir, "kata-agent")),
        "DRACUT_KVERSION={}".format(get_host_kernel_version()),
        "initrd",
    ]
    initrd_cmd = " ".join(initrd_cmd)
    result = run(
        initrd_cmd,
        shell=True,
        capture_output=True,
        cwd=join(initrd_base_dir, "tools", "osbuilder"),
    )
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())


def do_build_kernel(nocache=False):
    """
    This method builds the forked kernel needed in the SVSM. It is used for
    the __guest__ kernel only.
    """
    # First, generate the right config file: we start from our current one,
    # and make sure the following are set:
    # - CONFIG_KVM_AMD_SEV: for general SNP support in KVM
    # - CONFIG_TCG_PLATFORM: for vTPM support in the SVSM
    current_kernel_name = get_host_kernel_version()

    tmp_file = "/tmp/svsm_kernel_config"
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


def do_install(debug, clean):
    if clean and exists(SVSM_ROOT):
        result = run(f"sudo rm -rf {SVSM_ROOT}", shell=True, capture_output=True)
        assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())

    run(f"sudo mkdir -p ${SVSM_ROOT}", shell=True, check=True)

    # Install guest kernel
    copy_from_ctr_image(
        SVSM_KERNEL_IMAGE_TAG,
        ["/git/coconut-svsm/linux/arch/x86/boot/bzImage"],
        [join(SVSM_ROOT, "share", "sc2", "vmlinuz-kata-containers-sc2")],
        requires_sudo=True,
    )

    # Install QEMU and OVMF
    ctr_paths = [
        join(SVSM_ROOT, "bin", "qemu-system-x86_64"),
        join(SVSM_QEMU_DATA_DIR, "qemu"),
        "/git/coconut-svsm/edk2/Build/OvmfX64/RELEASE_GCC5/FV/OVMF.fd",
    ]
    host_paths = [
        join(SVSM_ROOT, "bin", "qemu-system-x86_64"),
        join(SVSM_QEMU_DATA_DIR, "qemu"),
        join(SVSM_ROOT, "share", "ovmf", "OVMF.fd"),
    ]
    copy_from_ctr_image(SVSM_QEMU_IMAGE_TAG, ctr_paths, host_paths, requires_sudo=True)

    # Prepare the guest's initrd
    do_build_initrd(clean=clean)

    # Install SVSM's IGVM image
    copy_from_ctr_image(
        SVSM_IMAGE_TAG,
        ["/git/coconut-svsm/svsm/bin/coconut-qemu.igvm"],
        [join(SVSM_ROOT, "share", "igvm", "coconut-qemu.igvm")],
        requires_sudo=True,
    )


# ------------------------------------------------------------------------------
# Entry-point tasks
# ------------------------------------------------------------------------------


@task
def build_guest_kernel(ctx, nocache=False, push=False):
    """
    Build the host/guest kernel fork to use with the SVSM
    """
    do_build_kernel(nocache=nocache)


@task
def build_initrd(ctx, clean=False):
    """
    Generate an initrd with the kata agent and the different kernel modules.
    """
    do_build_initrd(clean=clean)


@task
def build_qemu(ctx, nocache=False, push=False):
    """
    Build the QEMU fork for its use with the SVSM
    """
    do_build_qemu(nocache=nocache)

    if push:
        run(f"docker push {SVSM_QEMU_IMAGE_TAG}", shell=True, check=True)


@task
def build_svsm(ctx, nocache=False):
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
def install(ctx, clean=False):
    """
    Install guest kernel, QEMU, OVMF, and SVSM IGVM image
    """
    do_install(debug=False, clean=clean)
