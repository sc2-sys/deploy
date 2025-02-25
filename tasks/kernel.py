from invoke import task
from os import makedirs
from os.path import exists, join
from shutil import rmtree
from tasks.util.env import KATA_CONFIG_DIR, KATA_IMG_DIR, KATA_RUNTIMES, SC2_RUNTIMES
from tasks.util.kata import KATA_SOURCE_DIR, copy_from_kata_workon_ctr
from tasks.util.kernel import grub_update_default_kernel
from tasks.util.toml import update_toml
from tasks.util.versions import GUEST_KERNEL_VERSION
from subprocess import run


def build_guest(debug=False, hot_replace=False):
    """
    Build the guest kernel.

    We use Kata's build-kernel.sh to build the guest kernel. Note that, for
    the time being, there is no difference between SC2 and non-SC2 guest
    kernels. We still need to update them all, because our manual rootfs
    build requires a manual kernel build too (for some reason).
    """
    kernel_build_dir = "/tmp/sc2-guest-kernel-build-dir"

    if exists(kernel_build_dir):
        run(f"sudo rm -rf {kernel_build_dir}", shell=True, check=True)

    makedirs(kernel_build_dir)
    makedirs(join(kernel_build_dir, "kernel"))
    makedirs(join(kernel_build_dir, "scripts"))

    script_files = [
        "kernel/build-kernel.sh",
        "kernel/configs",
        "kernel/kata_config_version",
        "kernel/patches",
        "scripts/apply_patches.sh",
        "scripts/lib.sh",
    ]

    for ctr_path, host_path in zip(
        [
            join(
                # WARNING: for the time being it is OK to copy from the SC2
                # Kata source dir because there is no difference between
                # SC2 and non-SC2 guest kernels, but this is something we
                # should keep in mind.
                KATA_SOURCE_DIR,
                "tools/packaging",
                script,
            )
            for script in script_files
        ],
        [join(kernel_build_dir, script) for script in script_files],
    ):
        copy_from_kata_workon_ctr(
            ctr_path, host_path, sudo=False, debug=debug, hot_replace=hot_replace
        )

    # The -V option enables dm-verity support in the guest (technically only
    # needed for SC2)
    build_kernel_base_cmd = [
        f"./build-kernel.sh -x -V -f -v {GUEST_KERNEL_VERSION}",
        "-u 'https://cdn.kernel.org/pub/linux/kernel/v{}.x/'".format(
            GUEST_KERNEL_VERSION.split(".")[0]
        ),
    ]
    build_kernel_base_cmd = " ".join(build_kernel_base_cmd)

    # Install APT deps needed to build guest kernel
    sudo_cmd = (
        "sudo DEBIAN_FRONTEND=noninteractive apt install -y bison flex "
        "libelf-dev libssl-dev make"
    )
    out = run(sudo_cmd, shell=True, capture_output=True)
    assert out.returncode == 0, "Error installing deps: {}".format(
        out.stderr.decode("utf-8")
    )

    for step in ["setup", "build"]:
        out = run(
            f"{build_kernel_base_cmd} {step}",
            shell=True,
            capture_output=True,
            cwd=join(kernel_build_dir, "kernel"),
        )
        assert out.returncode == 0, "Error building guest kernel: {}\n{}".format(
            out.stdout.decode("utf-8"), out.stderr.decode("utf-8")
        )
        if debug:
            print(out.stdout.decode("utf-8"))

    # Copy the built kernel into the desired path
    with open(join(kernel_build_dir, "kernel", "kata_config_version"), "r") as fh:
        kata_config_version = fh.read()
        kata_config_version = kata_config_version.strip()

    sc2_kernel_name = "vmlinuz-confidential-sc2.container"
    bzimage_src_path = join(
        kernel_build_dir,
        "kernel",
        f"kata-linux-{GUEST_KERNEL_VERSION}-{kata_config_version}",
        "arch",
        "x86",
        "boot",
        "bzImage",
    )
    bzimage_dst_path = join(KATA_IMG_DIR, sc2_kernel_name)
    run(f"sudo cp {bzimage_src_path} {bzimage_dst_path}", shell=True, check=True)

    # Update the paths in the config files
    for runtime in KATA_RUNTIMES + SC2_RUNTIMES:
        conf_file_path = join(KATA_CONFIG_DIR, "configuration-{}.toml".format(runtime))
        updated_toml_str = """
        [hypervisor.qemu]
        kernel = "{new_kernel_path}"
        """.format(
            new_kernel_path=bzimage_dst_path
        )
        update_toml(conf_file_path, updated_toml_str)


@task
def hot_replace_guest(ctx, debug=False):
    """
    Hot-replace guest kernel
    """
    build_guest(debug=debug, hot_replace=True)


@task
def install_host_kernel_from_upstream(ctx):
    # TODO: find a way to automate the grepping of deb files and kernel name
    kernel_ver = "6.13"
    kernel_name = f"{kernel_ver}.0-061300-generic"

    tmp_dir = f"/tmp/kernel-{kernel_ver}"
    if exists(tmp_dir):
        rmtree(tmp_dir)
    makedirs(tmp_dir)

    base_url = f"https://kernel.ubuntu.com/mainline/v{kernel_ver}/amd64/"
    # The order of this files in the array _matters_
    deb_files = [
        "linux-headers-6.13.0-061300_6.13.0-061300.202501302155_all.deb",
        f"linux-headers-{kernel_name}_6.13.0-061300.202501302155_amd64.deb",
        f"linux-modules-{kernel_name}_6.13.0-061300.202501302155_amd64.deb",
        f"linux-image-unsigned-{kernel_name}_6.13.0-061300.202501302155_amd64.deb",
    ]
    for deb_file in deb_files:
        result = run(
            f"wget {base_url}/{deb_file}", shell=True, capture_output=True, cwd=tmp_dir
        )
        assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())

    for deb_file in deb_files:
        result = run(
            f"sudo dpkg -i {deb_file}", shell=True, capture_output=True, cwd=tmp_dir
        )
        assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())

    grub_update_default_kernel(kernel_name)
