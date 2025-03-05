from invoke import task
from json import JSONDecodeError, loads as json_loads
from os import getgid, getuid
from os.path import exists, join
from subprocess import run
from tasks.util.containerd import wait_for_containerd_socket
from tasks.util.docker import copy_from_ctr_image, is_ctr_running
from tasks.util.env import (
    BIN_DIR,
    COCO_ROOT,
    CONTAINERD_CONFIG_FILE,
    CONTAINERD_CONFIG_ROOT,
    KATA_RUNTIMES,
    LOCAL_REGISTRY_URL,
    PROJ_ROOT,
    SC2_RUNTIMES,
    print_dotted_line,
)
from tasks.util.nydus_snapshotter import (
    NYDUS_SNAPSHOTTER_IMAGE_TAG,
    build_nydus_snapshotter_image,
)
from tasks.util.toml import read_value_from_toml, update_toml
from tasks.util.versions import NYDUS_SNAPSHOTTER_VERSION
from time import sleep

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

NYDUS_SNAPSHOTTER_BINARY_NAMES = [
    "containerd-nydus-grpc",
    "nydus-overlayfs",
]
NYDUS_SNAPSHOTTER_CTR_BINPATH = "/go/src/github.com/sc2-sys/nydus-snapshotter/bin"
NYDUS_SNAPSHOTTER_HOST_BINPATH = "/opt/confidential-containers/bin"

# You can see all options to configure the  nydus-snapshotter here:
# https://github.com/containerd/nydus-snapshotter/blob/main/misc/snapshotter/config.toml


def do_purge(debug=False):
    """
    Purging the snapshotters for a fresh-start is a two step process. First,
    we need to remove all nydus metadata. This can be achieved by just
    bluntly removing `/var/lib/containerd-nydus-*`. Secondly, we need to
    reset a map that we keep in containerd's image store of what images
    have we pulled with which snapshotters. This is, essentially, what
    we see when we run `sudo crictl images`. There's no easy way to clear
    just this map, so what we do is remove all the images that we may have
    used.
    """

    # Clear nydus-snapshots
    for snap in [NYDUS_SNAPSHOTTER_HOST_SHARE_NAME, NYDUS_SNAPSHOTTER_GUEST_PULL_NAME]:
        run(f"sudo rm -rf /var/lib/containerd-{snap}", shell=True, check=True)

    # Clear all possibly used images (only images in our registry, or the
    # pause container images)
    tmp_out = "/tmp/cmd_output"
    cmd = (
        "sudo crictl --runtime-endpoint unix:///run/containerd/containerd.sock"
        f" images -o json > {tmp_out} 2> /dev/null"
    )
    rm_cmd = "sudo crictl --runtime-endpoint unix:///run/containerd/containerd.sock rmi"
    try:
        run(cmd, shell=True, check=True)
        with open(tmp_out, "r") as fh:
            stdout = fh.read().strip()
        data = json_loads(stdout)
    except JSONDecodeError as e:
        stderr = run(cmd, shell=True, capture_output=True).stderr.decode("utf-8")
        print(f"ERROR: run command: {cmd}, got stdout: {stdout}, stderr: {stderr}")
        raise e
    for image_data in data["images"]:
        # Try matching both by repoTags and repoDigests (the former is sometimes
        # empty)
        if any(
            [
                tag.startswith(LOCAL_REGISTRY_URL)
                for tag in image_data["repoTags"] + image_data["repoDigests"]
            ]
        ):
            result = run(
                "{} {} 2> /dev/null".format(rm_cmd, image_data["id"]),
                shell=True,
                capture_output=True,
            )
            assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
            if debug:
                print(result.stdout.decode("utf-8").strip())

            continue

        if any(
            [
                tag.startswith("registry.k8s.io/pause")
                for tag in image_data["repoTags"] + image_data["repoDigests"]
            ]
        ):
            result = run(
                "{} {} 2> /dev/null".format(rm_cmd, image_data["id"]),
                shell=True,
                capture_output=True,
            )
            assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
            if debug:
                print(result.stdout.decode("utf-8").strip())

            continue

    restart_nydus_snapshotter()

    # After restarting we need to wait for containerd's GC to clean-up the
    # metadata database
    for snap in [NYDUS_SNAPSHOTTER_HOST_SHARE_NAME, NYDUS_SNAPSHOTTER_GUEST_PULL_NAME]:
        wait_for_snapshot_metadata_to_be_gced(snap, debug=debug)


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
export_mode = "layer_block_with_verity"
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
        do_purge(debug=debug)

    # Restart the nydus service
    restart_nydus_snapshotter()

    print("Success!")


def restart_nydus_snapshotter():
    run("sudo service nydus-snapshotter restart", shell=True, check=True)


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


def wait_for_snapshot_metadata_to_be_gced(snapshotter, debug=False):
    """
    After restarting containerd it may take a while for the GC to kick in and
    delete the metadata corresponding to previous snapshots. This metadata
    is stored in a Bolt DB in /var/lib/containerd/io.containerd.metadata.v1.bolt/meta.db

    Annoyingly, it is hard to manually delete files from the database w/out
    writting a small Go script. Instead, we rely on the bbolt CLI tool to
    poll the DB until the GC has done its job.
    """
    bbolt_path = join(BIN_DIR, "bbolt")
    db_path = "/var/lib/containerd/io.containerd.metadata.v1.bolt/meta.db"
    tmp_db_path = "/tmp/containerd_meta_copy.db"
    bbolt_cmd = f"{bbolt_path} keys {tmp_db_path} v1 k8s.io snapshots {snapshotter}"

    while True:
        # Make a user-owned copy of the DB (bbolt complains otherwise)
        run(f"sudo cp {db_path} {tmp_db_path}", shell=True, check=True)
        run(
            "sudo chown {}:{} {}".format(getuid(), getgid(), tmp_db_path),
            shell=True,
            check=True,
        )

        result = run(bbolt_cmd, shell=True, capture_output=True)
        stdout = result.stdout.decode("utf-8").strip()

        if result.returncode == 1:
            # This can be a benign error if the snapshotter has not been used
            # at all, never
            if stdout == "bucket not found":
                if debug:
                    print(f"WARNING: bucket {snapshotter} not found in metadata")
                    run(f"rm {tmp_db_path}", shell=True, check=True)
                return
            else:
                print(
                    "ERROR: running bbolt command: stdout: {}, stderr: {}".format(
                        stdout, result.stderr.decode("utf-8").strip()
                    )
                )
                run(f"rm {tmp_db_path}", shell=True, check=True)

                raise RuntimeError("Error running bbolt command!")
        elif result.returncode == 0:
            if len(stdout) == 0:
                run(f"rm {tmp_db_path}", shell=True, check=True)
                return

            print(
                "Got {} snapshot's metadata for snapshotter: {}".format(
                    len(stdout.split("\n")), snapshotter
                )
            )
            sleep(2)
        else:
            print(
                "ERROR: running bbolt command: stdout: {}, stderr: {}".format(
                    stdout, result.stderr.decode("utf-8").strip()
                )
            )
            run(f"rm {tmp_db_path}", shell=True, check=True)

            raise RuntimeError("Error running bbolt command!")


# ------------------------------------------------------------------------------
# Main entrypoint tasks
# ------------------------------------------------------------------------------


@task
def build(ctx, nocache=False, push=False):
    """
    Build the nydus-snapshotter image
    """
    build_nydus_snapshotter_image(nocache, push)


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
def purge(ctx):
    """
    Remove all cached snapshots in the snapshotter cache
    """
    wait_for_containerd_socket()
    do_purge(debug=True)


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
