from invoke import task
from os.path import join
from subprocess import run
from tasks.util.docker import is_ctr_running
from tasks.util.env import COCO_ROOT, GHCR_URL, GITHUB_ORG, PROJ_ROOT, print_dotted_line
from tasks.util.toml import update_toml
from tasks.util.versions import NYDUS_SNAPSHOTTER_VERSION

NYDUS_SNAPSHOTTER_CONFIG_FILE = join(
    COCO_ROOT, "share", "nydus-snapshotter", "config-coco-guest-pulling.toml"
)
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


def install(debug=False, clean=False):
    """
    Install the nydus snapshotter binaries
    """
    print_dotted_line(f"Installing nydus-snapshotter (v{NYDUS_SNAPSHOTTER_VERSION})")

    docker_cmd = "docker run -td --name {} {} bash".format(
        NYDUS_SNAPSHOTTER_CTR_NAME, NYDUS_SNAPSHOTTER_IMAGE_TAG
    )
    result = run(docker_cmd, shell=True, capture_output=True)
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
    if debug:
        print(result.stdout.decode("utf-8").strip())

    def cleanup():
        docker_cmd = "docker rm -f {}".format(NYDUS_SNAPSHOTTER_CTR_NAME)
        result = run(docker_cmd, shell=True, capture_output=True)
        assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
        if debug:
            print(result.stdout.decode("utf-8").strip())

    for binary in NYDUS_SNAPSHOTTER_BINARY_NAMES:
        docker_cmd = "sudo docker cp {}:{}/{} {}/{}".format(
            NYDUS_SNAPSHOTTER_CTR_NAME,
            NYDUS_SNAPSHOTTER_CTR_BINPATH,
            binary,
            NYDUS_SNAPSHOTTER_HOST_BINPATH,
            binary,
        )
        result = run(docker_cmd, shell=True, capture_output=True)
        if result.returncode != 0:
            cleanup()
            print(result.stderr.decode("utf-8").strip())
            raise RuntimeError("Error copying from nydus snapshotter workon!")

        if debug:
            print(result.stdout.decode("utf-8").strip())

    cleanup()

    # Remove all nydus config for a clean start
    if clean:
        run("sudo rm -rf /var/lib/containerd-nydus", shell=True, check=True)

    # Restart the nydus service
    restart_nydus_snapshotter()

    print("Success!")


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


@task
def set_log_level(ctx, log_level):
    """
    Set the log level for the nydus snapshotter
    """
    allowed_log_levels = ["info", "debug"]
    if log_level not in allowed_log_levels:
        print(
            "Unsupported log level '{}'. Must be one in: {}".format(
                log_level, allowed_log_levels
            )
        )
        return

    updated_toml_str = """
    [log]
    level = "{log_level}"
    """.format(
        log_level=log_level
    )
    update_toml(NYDUS_SNAPSHOTTER_CONFIG_FILE, updated_toml_str)

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
