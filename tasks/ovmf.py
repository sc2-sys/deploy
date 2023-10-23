from invoke import task
from os.path import join
from subprocess import run
from tasks.util.env import BIN_DIR, KATA_CONFIG_DIR, KATA_RUNTIMES, PROJ_ROOT
from tasks.util.toml import update_toml

OVMF_IMAGE_TAG = "ovmf-build"


def do_ovmf_build(target):
    docker_cmd = "docker build -t {} -f {} .".format(
        OVMF_IMAGE_TAG, join(PROJ_ROOT, "docker", "ovmf.dockerfile")
    )
    env = {"TARGET": target}
    run(docker_cmd, shell=True, check=True, cwd=PROJ_ROOT, env=env)


def copy_ovmf_from_src(dst_path):
    """
    Copy a custom build of OVMF into the destination path
    """
    do_ovmf_build("DEBUG")

    # Copy the debug-built OVMF into the destiantion path
    tmp_ctr_name = "tmp_ovmf"
    docker_cmd = "docker run -td --name {} {}".format(tmp_ctr_name, OVMF_IMAGE_TAG)
    run(docker_cmd, shell=True, check=True)

    ctr_fd_path = "/usr/src/edk2/Build/AmdSev/DEBUG_GCC5/FV/OVMF.fd"
    docker_cmd = "docker cp {}:{} {}".format(
        tmp_ctr_name,
        ctr_fd_path,
        dst_path,
    )
    run(docker_cmd, shell=True, check=True)

    run("docker rm -f {}".format(tmp_ctr_name), shell=True, check=True)


@task
def build(ctx, target="DEBUG"):
    """
    Build the OVMF work-on container image
    """
    do_ovmf_build(target)


@task
def set_log_level(ctx, log_level):
    """
    Set OVMF's log level, must be one in: info, debug

    In order to toggle debug logging in OVMF, we need to update the QEMU
    command line to include a couple of OVMF flags. To change the QEMU command
    line, we use a bash wrapper with the extra flags, and point Kata to the
    wrapper script.

    In addition, we need to re-compile OVMF from scratch with the DEBUG
    target.

    Note that using a DEBUG version of OVMF is only supported with the qemu-sev
    runtime class.
    """
    allowed_log_levels = ["info", "debug"]
    if log_level not in allowed_log_levels:
        print(
            "Unsupported log level '{}'. Must be one in: {}".format(
                log_level, allowed_log_levels
            )
        )
        return

    default_qemu_path = "/opt/confidential-containers/bin/qemu-system-x86_64"
    wrapper_qemu_path = join(BIN_DIR, "qemu_wrapper_ovmf_logging.sh")
    qemu_path = default_qemu_path if log_level == "info" else wrapper_qemu_path

    default_fw_path = "/opt/confidential-containers/share/ovmf/AMDSEV.fd"
    debug_fw_path = "/opt/confidential-containers/share/ovmf/AMDSEV_CSG.fd"
    copy_ovmf_from_src(debug_fw_path)
    fw_path = default_fw_path if log_level == "info" else debug_fw_path

    updated_toml_str = """
    [hypervisor.qemu]
    valid_hypervisor_paths = [ "{qemu_path}",]
    firmware = "{fw_path}"
    """.format(
        qemu_path=qemu_path,
        fw_path=fw_path
    )

    conf_file_path = join(KATA_CONFIG_DIR, "configuration-qemu-sev.toml")
    update_toml(conf_file_path, updated_toml_str)
