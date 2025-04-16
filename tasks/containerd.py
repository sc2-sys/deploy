from invoke import task
from os import stat
from os.path import join
from subprocess import run
from tasks.util.containerd import (
    CONTAINERD_IMAGE_TAG,
    build_containerd_image,
    is_containerd_active,
    restart_containerd,
    wait_for_containerd_socket,
)
from tasks.util.docker import copy_from_ctr_image, is_ctr_running
from tasks.util.env import (
    BIN_DIR,
    CONF_FILES_DIR,
    CONTAINERD_CONFIG_FILE,
    CONTAINERD_CONFIG_ROOT,
    PROJ_ROOT,
    print_dotted_line,
)
from tasks.util.toml import update_toml
from tasks.util.versions import CONTAINERD_VERSION, GO_VERSION
from time import sleep

CONTAINERD_CTR_NAME = "containerd-workon"

CONTAINERD_BINARY_NAMES = [
    "containerd",
    "containerd-shim",
    "containerd-shim-runc-v1",
    "containerd-shim-runc-v2",
]
CONTAINERD_CTR_BINPATH = "/go/src/github.com/sc2-sys/containerd/bin"
CONTAINERD_HOST_BINPATH = "/usr/bin"

from tasks.util.proxy import check_return_proxy, configure_containerd_proxy

@task
def build(ctx, nocache=False, push=False):
    """
    Build the containerd fork for SC2
    """
    build_containerd_image(nocache=nocache, push=push)


@task
def cli(ctx, mount_path=join(PROJ_ROOT, "..", "containerd")):
    """
    Get a working environment for containerd
    """
    if not is_ctr_running(CONTAINERD_CTR_NAME):
        docker_cmd = [
            "docker run",
            "-d -it",
            # The container path comes from the dockerfile in:
            # ./docker/containerd.dockerfile
            f"-v {mount_path}:/go/src/github.com/sc2-sys/containerd",
            "--name {}".format(CONTAINERD_CTR_NAME),
            CONTAINERD_IMAGE_TAG,
            "bash",
        ]
        docker_cmd = " ".join(docker_cmd)
        run(docker_cmd, shell=True, check=True, cwd=PROJ_ROOT)

    run("docker exec -it {} bash".format(CONTAINERD_CTR_NAME), shell=True, check=True)


@task
def stop(ctx):
    """
    Stop the containerd work-on container
    """
    result = run(
        "docker rm -f {}".format(CONTAINERD_CTR_NAME),
        shell=True,
        check=True,
        capture_output=True,
    )
    assert result.returncode == 0


def set_log_level(log_level):
    """
    Set containerd's log level, must be one in: info, debug
    """
    updated_toml_str = """
    [debug]
    level = "{log_level}"
    """.format(
        log_level=log_level
    )
    update_toml(CONTAINERD_CONFIG_FILE, updated_toml_str)

    restart_containerd()


@task
def hot_replace(ctx):
    """
    Replace containerd binaries from running workon container
    """
    if not is_ctr_running(CONTAINERD_CTR_NAME):
        print("Must have the work-on container running to hot replace!")
        print("Consider running: inv containerd.cli ")
        return

    for binary in CONTAINERD_BINARY_NAMES:
        print(
            (
                f"cp {CONTAINERD_CTR_NAME}:{CONTAINERD_CTR_BINPATH}/{binary} "
                f"{CONTAINERD_HOST_BINPATH}/{binary}"
            )
        )
        docker_cmd = (
            f"sudo docker cp {CONTAINERD_CTR_NAME}:{CONTAINERD_CTR_BINPATH}/"
            f"{binary} {CONTAINERD_HOST_BINPATH}/{binary}"
        )
        run(docker_cmd, shell=True, check=True)

    restart_containerd()


def install(debug=False, clean=False):
    """
    Install (and build) containerd from source
    """
    print_dotted_line(f"Installing containerd (v{CONTAINERD_VERSION})")

    if is_containerd_active():
        run("sudo service containerd stop", shell=True, check=True)

    ctr_base_path = "/go/src/github.com/sc2-sys/containerd/bin"
    host_base_path = "/usr/bin"

    host_binaries = [join(host_base_path, binary) for binary in CONTAINERD_BINARY_NAMES]
    ctr_binaries = [join(ctr_base_path, binary) for binary in CONTAINERD_BINARY_NAMES]
    copy_from_ctr_image(
        CONTAINERD_IMAGE_TAG, ctr_binaries, host_binaries, requires_sudo=True
    )

    # Clean-up all runtime files for a clean start
    if clean:
        run("sudo rm -rf /var/lib/containerd", shell=True, check=True)

    # Configure the CNI (see containerd/scripts/setup/install-cni)
    if clean:
        cni_conf_file = "10-containerd-net.conflist"
        cni_dir = "/etc/cni/net.d"
        run(f"sudo mkdir -p {cni_dir}", shell=True, check=True)
        cp_cmd = "sudo cp {} {}".format(
            join(CONF_FILES_DIR, cni_conf_file), join(cni_dir, cni_conf_file)
        )
        run(cp_cmd, shell=True, check=True)

    # Populate the default config file for a clean start
    run(f"sudo mkdir -p {CONTAINERD_CONFIG_ROOT}", shell=True, check=True)
    if clean:
        config_cmd = "{}/containerd config default > {}".format(
            host_base_path, CONTAINERD_CONFIG_FILE
        )
        config_cmd = "sudo bash -c '{}'".format(config_cmd)
        run(config_cmd, shell=True, check=True)
        # Install proxy for containerd
        if check_return_proxy():
            configure_containerd_proxy()

    # Restart containerd service
    run("sudo service containerd start", shell=True, check=True)

    # Sanity check
    if stat(CONTAINERD_CONFIG_FILE).st_size == 0:
        raise RuntimeError("containerd config file is empty!")

    # Wait for containerd to be ready
    sleep(2)
    while not is_containerd_active():
        if debug:
            print("Waiting for containerd to be active...")

        sleep(2)

    # Then make sure we can dial the socket
    wait_for_containerd_socket()

    print("Success!")


def install_bbolt(debug=False, clean=False):
    print_dotted_line("Installing bbolt")

    wait_for_containerd_socket()

    tmp_ctr_name = "bbolt_install"
    if is_ctr_running(tmp_ctr_name):
        result = run(f"docker rm -f {tmp_ctr_name}", shell=True, capture_output=True)
        assert result.returncode == 0

    def rm_container():
        result = run(f"docker rm -f {tmp_ctr_name}", shell=True, capture_output=True)
        assert result.returncode == 0

    result = run(
        f"docker run -d -it --name {tmp_ctr_name} golang:{GO_VERSION} bash",
        shell=True,
        capture_output=True,
    )
    if result.returncode != 0:
        print(result.stderr.decode("utf-8").strip()),
        rm_container()
        raise RuntimeError("Error running container")

    result = run(
        f"docker exec {tmp_ctr_name} go install go.etcd.io/bbolt/cmd/bbolt@latest",
        shell=True,
        capture_output=True,
    )
    if result.returncode != 0:
        print(result.stderr.decode("utf-8").strip()),
        rm_container()
        raise RuntimeError("Error execing into container")
    if debug:
        print(result.stdout.decode("utf-8").strip())

    result = run(
        f"docker cp {tmp_ctr_name}:/go/bin/bbolt {BIN_DIR}/bbolt",
        shell=True,
        capture_output=True,
    )
    if result.returncode != 0:
        print(result.stderr.decode("utf-8").strip()),
        rm_container()
        raise RuntimeError("Error cp-ing from container")
    if debug:
        print(result.stdout.decode("utf-8").strip())

    rm_container()

    print("Success!")
