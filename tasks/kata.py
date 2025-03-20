from invoke import task
from os.path import abspath, join
from subprocess import run
from tasks.util.containerd import restart_containerd
from tasks.util.env import (
    KATA_CONFIG_DIR,
    KATA_IMG_DIR,
    KATA_ROOT,
    KATA_RUNTIMES,
    KATA_WORKON_CTR_NAME,
    PROJ_ROOT,
    SC2_RUNTIMES,
)
from tasks.util.kata import (
    build_kata_image,
    replace_agent as replace_kata_agent,
    replace_shim as replace_kata_shim,
    run_kata_workon_ctr,
    stop_kata_workon_ctr,
)
from tasks.util.toml import read_value_from_toml, update_toml


def set_log_level(log_level):
    """
    Set kata's log level, must be one in: info, debug
    """
    enable_debug = str(log_level == "debug").lower()

    for runtime in KATA_RUNTIMES + SC2_RUNTIMES:
        conf_file_path = join(KATA_CONFIG_DIR, "configuration-{}.toml".format(runtime))
        updated_toml_str = """
        [hypervisor.qemu]
        enable_debug = {enable_debug}

        [agent.kata]
        enable_debug = {enable_debug}
        debug_console_enabled = {enable_debug}

        [runtime]
        enable_debug = {enable_debug}
        """.format(
            enable_debug=enable_debug
        )
        update_toml(conf_file_path, updated_toml_str)


@task
def build(ctx, nocache=False, push=False):
    """
    Build the Kata Containers workon docker image
    """
    build_kata_image(nocache, push)


@task
def cli(
    ctx,
    mount_path=join(PROJ_ROOT, "..", "kata-containers"),
    gc_mount_path=join(PROJ_ROOT, "..", "guest-components"),
):
    """
    Get a working environemnt to develop Kata
    """
    if mount_path is not None:
        mount_path = abspath(mount_path)

    if gc_mount_path is not None:
        gc_mount_path = abspath(gc_mount_path)

    run_kata_workon_ctr(mount_path=mount_path, gc_mount_path=gc_mount_path)
    run("docker exec -it {} bash".format(KATA_WORKON_CTR_NAME), shell=True, check=True)


@task
def enable_annotation(ctx, annotation, runtime="qemu-snp-sc2"):
    """
    Enable Kata annotation in config file
    """
    conf_file_path = join(KATA_CONFIG_DIR, "configuration-{}.toml".format(runtime))
    enabled_annotations = read_value_from_toml(
        conf_file_path, "hypervisor.qemu.enable_annotations"
    )

    if annotation in enabled_annotations:
        return

    enabled_annotations.append(annotation)
    updated_toml_str = """
    [hypervisor.qemu]
    enable_annotations = [ {ann} ]
    """.format(
        ann=",".join([f'"{a}"' for a in enabled_annotations])
    )
    update_toml(conf_file_path, updated_toml_str)


@task
def hot_replace_agent(ctx, debug=False, runtime="qemu-snp-sc2"):
    """
    Replace Kata Agent from built version in work-on container
    """
    replace_kata_agent(
        dst_initrd_path=join(
            KATA_IMG_DIR, "kata-containers-initrd-confidential-sc2.img"
        ),
        dst_img_path=join(KATA_IMG_DIR, "kata-containers-confidential-sc2.img"),
        debug=debug,
        sc2=runtime in SC2_RUNTIMES,
        hot_replace=True,
    )


@task
def hot_replace_shim(ctx, runtime="qemu-snp-sc2"):
    """
    Replace Kata Shim from built version in work-on container
    """
    replace_kata_shim(
        dst_shim_binary=join(
            KATA_ROOT,
            "bin",
            (
                "containerd-shim-kata-sc2-v2"
                if runtime in SC2_RUNTIMES
                else "containerd-shim-kata-v2"
            ),
        ),
        sc2=runtime in SC2_RUNTIMES,
        hot_replace=True,
    )

    restart_containerd()


@task
def stop(ctx):
    """
    Remove the Kata developement environment
    """
    stop_kata_workon_ctr()
