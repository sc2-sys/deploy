from invoke import task
from os.path import exists, join
from subprocess import run
from tasks.util.docker import copy_from_ctr_image, is_ctr_running
from tasks.util.env import (
    COCO_ROOT,
    CONTAINERD_CONFIG_FILE,
    CONTAINERD_CONFIG_ROOT,
    GHCR_URL,
    GITHUB_ORG,
    KATA_RUNTIMES,
    PROJ_ROOT,
    SC2_RUNTIMES,
    print_dotted_line,
)
from tasks.util.toml import read_value_from_toml, update_toml
from tasks.util.versions import NYDUS_SNAPSHOTTER_VERSION

NYDUS_SNAPSHOTTER_GUEST_PULL_NAME = "nydus"
NYDUS_SNAPSHOTTER_HOST_SHARE_NAME = "nydus-hs"

NYDUS_SNAPSHOTTER_CONFIG_DIR = join(COCO_ROOT, "share", "nydus-snapshotter")
NYDUS_SNAPSHOTTER_GUEST_PULL_CONFIG = join(
    NYDUS_SNAPSHOTTER_CONFIG_DIR, "config-coco-guest-pulling.toml"
)
NYDUS_SNAPSHOTTER_HOST_SHARE_CONFIG = join(
    NYDUS_SNAPSHOTTER_CONFIG_DIR, "config-coco-host-sharing.toml"
)

NYDUS_SNAPSHOTTER_CONFIG_FILES = [
    NYDUS_SNAPSHOTTER_GUEST_PULL_CONFIG,
    NYDUS_SNAPSHOTTER_HOST_SHARE_CONFIG,
]
NYDUS_SNAPSHOTTER_CTR_NAME = "nydus-snapshotter-workon"
NYDUS_SNAPSHOTTER_IMAGE_TAG = (
    join(GHCR_URL, GITHUB_ORG, "nydus-snapshotter") + f":{NYDUS_SNAPSHOTTER_VERSION}"
)

NYDUS_SNAPSHOTTER_BINARY_NAMES = [
    "containerd-nydus-grpc",
    "nydus-overlayfs",
]
NYDUS_SNAPSHOTTER_CTR_BINPATH = "/go/src/github.com/sc2-sys/nydus-snapshotter/bin"
NYDUS_SNAPSHOTTER_HOST_BINPATH = "/opt/confidential-containers/bin"

# You can see all options to configure the  nydus-snapshotter here:
# https://github.com/containerd/nydus-snapshotter/blob/main/misc/snapshotter/config.toml


def restart_nydus_snapshotter():
    run("sudo service nydus-snapshotter restart", shell=True, check=True)


def do_purge():
    # Sometimes this may not be enough, and we need to manually delete images
    # using something like `sudo crictl rmi ...`
    for snap in [NYDUS_SNAPSHOTTER_HOST_SHARE_NAME, NYDUS_SNAPSHOTTER_GUEST_PULL_NAME]:
        run(f"sudo rm -rf /var/lib/containerd-{snap}", shell=True, check=True)

    restart_nydus_snapshotter()


@task
def purge(ctx):
    """
    Remove all cached snapshots in the snapshotter cache
    """
    do_purge()


def install(debug=False, clean=False):
    """
    Install the nydus snapshotter binaries
    """
    print_dotted_line(f"Installing nydus-snapshotter(s) (v{NYDUS_SNAPSHOTTER_VERSION})")

    host_binaries = [
        join(NYDUS_SNAPSHOTTER_HOST_BINPATH, binary)
        for binary in NYDUS_SNAPSHOTTER_BINARY_NAMES
    ]
    ctr_binaries = [
        join(NYDUS_SNAPSHOTTER_CTR_BINPATH, binary)
        for binary in NYDUS_SNAPSHOTTER_BINARY_NAMES
    ]
    copy_from_ctr_image(
        NYDUS_SNAPSHOTTER_IMAGE_TAG, ctr_binaries, host_binaries, requires_sudo=True
    )

    # We install nydus with host-sharing as a "different" snapshotter
    imports = read_value_from_toml(CONTAINERD_CONFIG_FILE, "imports")
    host_share_import_path = join(
        CONTAINERD_CONFIG_ROOT,
        "config.toml.d",
        f"{NYDUS_SNAPSHOTTER_HOST_SHARE_NAME}-snapshotter.toml",
    )
    if host_share_import_path not in imports:
        config_file = """
[proxy_plugins]
  [proxy_plugins.{}]
        type = "snapshot"
        address = "/run/containerd-nydus/containerd-nydus-grpc.sock"
""".format(
            NYDUS_SNAPSHOTTER_HOST_SHARE_NAME
        )

        cmd = """
sudo sh -c 'cat <<EOF > {destination_file}
{file_contents}
EOF'
""".format(
            destination_file=host_share_import_path,
            file_contents=config_file,
        )

        run(cmd, shell=True, check=True)

        imports += [host_share_import_path]
        updated_toml_str = """
        imports = [ {sn} ]
        """.format(
            sn=",".join([f'"{s}"' for s in imports])
        )
        update_toml(CONTAINERD_CONFIG_FILE, updated_toml_str)

    if not exists(NYDUS_SNAPSHOTTER_HOST_SHARE_CONFIG):
        host_sharing_config = """
version = 1
root = "/var/lib/containerd-{nydus_hs_name}"
address = "/run/containerd-nydus/containerd-nydus-grpc.sock"
daemon_mode = "none"

[system]
enable = true
address = "/run/containerd-nydus/system.sock"

[daemon]
fs_driver = "blockdev"
nydusimage_path = "{nydus_image_path}"

[remote]
skip_ssl_verify = true

[snapshot]
enable_kata_volume = true

[experimental.tarfs]
enable_tarfs = true
mount_tarfs_on_host = false
export_mode = "image_block_with_verity"
""".format(
            nydus_hs_name=NYDUS_SNAPSHOTTER_HOST_SHARE_NAME,
            nydus_image_path=join(COCO_ROOT, "bin", "nydus-image"),
        )

        cmd = """
sudo sh -c 'cat <<EOF > {destination_file}
{file_contents}
EOF'
""".format(
            destination_file=NYDUS_SNAPSHOTTER_HOST_SHARE_CONFIG,
            file_contents=host_sharing_config,
        )

        run(cmd, shell=True, check=True)

    # Remove all nydus config for a clean start
    if clean:
        do_purge()

    # Restart the nydus service
    restart_nydus_snapshotter()

    print("Success!")


@task
def foo(ctx):
    install(clean=True, debug=False)


@task
def build(ctx, nocache=False, push=False):
    """
    Build the nydus-snapshotter image
    """
    docker_cmd = "docker build {} -t {} -f {} .".format(
        "--no-cache" if nocache else "",
        NYDUS_SNAPSHOTTER_IMAGE_TAG,
        join(PROJ_ROOT, "docker", "nydus_snapshotter.dockerfile"),
    )
    run(docker_cmd, shell=True, check=True, cwd=PROJ_ROOT)

    if push:
        run(f"docker push {NYDUS_SNAPSHOTTER_IMAGE_TAG}", shell=True, check=True)


def set_log_level(log_level):
    """
    Set the log level for the nydus snapshotter
    """
    for config_file in NYDUS_SNAPSHOTTER_CONFIG_FILES:
        updated_toml_str = """
        [log]
        level = "{log_level}"
        """.format(
            log_level=log_level
        )
        update_toml(config_file, updated_toml_str)

    restart_nydus_snapshotter()


@task
def cli(ctx, mount_path=join(PROJ_ROOT, "..", "nydus-snapshotter")):
    """
    Get a working environment for the nydus-snapshotter
    """
    if not is_ctr_running(NYDUS_SNAPSHOTTER_CTR_NAME):
        docker_cmd = [
            "docker run",
            "-d -it",
            # The container path comes from the dockerfile in:
            # ./docker/nydus_snapshotter.dockerfile
            f"-v {mount_path}:/go/src/github.com/sc2-sys/nydus-snapshotter",
            "--name {}".format(NYDUS_SNAPSHOTTER_CTR_NAME),
            NYDUS_SNAPSHOTTER_IMAGE_TAG,
            "bash",
        ]
        docker_cmd = " ".join(docker_cmd)
        run(docker_cmd, shell=True, check=True, cwd=PROJ_ROOT)

    run(
        "docker exec -it {} bash".format(NYDUS_SNAPSHOTTER_CTR_NAME),
        shell=True,
        check=True,
    )


@task
def stop(ctx):
    """
    Stop the nydus-snapshotter work-on container
    """
    result = run(
        "docker rm -f {}".format(NYDUS_SNAPSHOTTER_CTR_NAME),
        shell=True,
        check=True,
        capture_output=True,
    )
    assert result.returncode == 0


@task
def hot_replace(ctx):
    """
    Replace nydus-snapshotter binaries from running workon container
    """
    if not is_ctr_running(NYDUS_SNAPSHOTTER_CTR_NAME):
        print("Must have the work-on container running to hot replace!")
        print("Consider running: inv nydus-snapshotter.cli ")

    for binary in NYDUS_SNAPSHOTTER_BINARY_NAMES:
        print(
            (
                f"cp {NYDUS_SNAPSHOTTER_CTR_NAME}:{NYDUS_SNAPSHOTTER_CTR_BINPATH}"
                f"/{binary} {NYDUS_SNAPSHOTTER_HOST_BINPATH}/{binary}"
            )
        )
        docker_cmd = (
            "sudo docker cp "
            f"{NYDUS_SNAPSHOTTER_CTR_NAME}:{NYDUS_SNAPSHOTTER_CTR_BINPATH}/"
            f"{binary} {NYDUS_SNAPSHOTTER_HOST_BINPATH}/{binary}"
        )
        run(docker_cmd, shell=True, check=True)

    restart_nydus_snapshotter()


@task
def set_mode(ctx, mode):
    """
    Set the nydus-snapshotter operation mode: 'guest-pull', or 'host-share'
    """
    if mode not in ["guest-pull", "host-share"]:
        print(f"ERROR: unrecognised nydus-snapshotter mode: {mode}")
        print("ERROR: mode must be one in: ['guest-pull', 'host-share']")
        return

    config_file = (
        NYDUS_SNAPSHOTTER_HOST_SHARE_CONFIG
        if mode == "host-share"
        else NYDUS_SNAPSHOTTER_GUEST_PULL_CONFIG
    )
    exec_start = (
        f"{NYDUS_SNAPSHOTTER_HOST_BINPATH}/containerd-nydus-grpc "
        f"--config {config_file} --log-to-stdout"
    )

    service_config = """
[Unit]
Description=Nydus snapshotter
After=network.target local-fs.target
Before=containerd.service

[Service]
ExecStart={}

[Install]
RequiredBy=containerd.service
""".format(
        exec_start
    )

    service_path = "/etc/systemd/system/nydus-snapshotter.service"
    cmd = """
sudo sh -c 'cat <<EOF > {destination_file}
{file_contents}
EOF'
""".format(
        destination_file=service_path,
        file_contents=service_config,
    )
    run(cmd, shell=True, check=True)

    # Update all runtime configurations to use the right snapshotter. We
    # _always_ avoid having both snapshotters co-existing
    snap_name = (
        NYDUS_SNAPSHOTTER_HOST_SHARE_NAME
        if mode == "host-share"
        else NYDUS_SNAPSHOTTER_GUEST_PULL_NAME
    )
    for runtime in KATA_RUNTIMES + SC2_RUNTIMES:
        updated_toml_str = """
        [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.kata-{runtime_name}]
        snapshotter = "{snapshotter_name}"
        """.format(
            runtime_name=runtime, snapshotter_name=snap_name
        )
        update_toml(CONTAINERD_CONFIG_FILE, updated_toml_str)

    # Reload systemd to apply the new service configuration
    run("sudo systemctl daemon-reload", shell=True, check=True)

    restart_nydus_snapshotter()
