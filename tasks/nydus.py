from invoke import task
from os.path import join
from subprocess import run
from tasks.util.docker import copy_from_ctr_image, is_ctr_running
from tasks.util.env import COCO_ROOT, GHCR_URL, GITHUB_ORG, PROJ_ROOT, print_dotted_line
from tasks.util.nydus import NYDUSIFY_PATH
from tasks.util.versions import NYDUS_VERSION

NYDUS_CTR_NAME = "nydus-workon"
NYDUS_IMAGE_TAG = join(GHCR_URL, GITHUB_ORG, "nydus") + f":{NYDUS_VERSION}"

NYDUS_IMAGE_CTR_PATH = "/go/src/github.com/sc2-sys/nydus/target/release/nydus-image"
NYDUS_IMAGE_HOST_PATH = join(COCO_ROOT, "bin", "nydus-image")


@task
def build(ctx, nocache=False, push=False):
    """
    Build the nydusd and nydus-snapshotter images
    """
    docker_cmd = "docker build {} -t {} -f {} .".format(
        "--no-cache" if nocache else "",
        NYDUS_IMAGE_TAG,
        join(PROJ_ROOT, "docker", "nydus.dockerfile"),
    )
    run(docker_cmd, shell=True, check=True, cwd=PROJ_ROOT)

    if push:
        run(f"docker push {NYDUS_IMAGE_TAG}", shell=True, check=True)


def do_install():
    print_dotted_line(f"Installing nydus image services (v{NYDUS_VERSION})")

    # Non root-owned binaries
    ctr_bin = ["/go/src/github.com/sc2-sys/nydus/contrib/nydusify/cmd/nydusify"]
    host_bin = [NYDUSIFY_PATH]
    copy_from_ctr_image(NYDUS_IMAGE_TAG, ctr_bin, host_bin, requires_sudo=False)

    # Root-owned binaries
    # The host-pull functionality requires nydus-image >= 2.3.0, but the one
    # installed with the daemon is 2.2.4
    ctr_bin = [NYDUS_IMAGE_CTR_PATH]
    host_bin = [NYDUS_IMAGE_HOST_PATH]
    copy_from_ctr_image(NYDUS_IMAGE_TAG, ctr_bin, host_bin, requires_sudo=True)

    print("Success!")


@task
def install(ctx):
    """
    Install the nydusify CLI tool
    """
    do_install()


@task
def cli(ctx, mount_path=join(PROJ_ROOT, "..", "nydus")):
    """
    Get a working environemnt for nydusd
    """
    if not is_ctr_running(NYDUS_CTR_NAME):
        docker_cmd = [
            "docker run",
            "-d -it",
            # The container path comes from the dockerfile in:
            # ./docker/nydus.dockerfile
            f"-v {mount_path}:/go/src/github.com/sc2-sys/nydus",
            "--name {}".format(NYDUS_CTR_NAME),
            NYDUS_IMAGE_TAG,
            "bash",
        ]
        docker_cmd = " ".join(docker_cmd)
        run(docker_cmd, shell=True, check=True, cwd=PROJ_ROOT)

    run(
        "docker exec -it {} bash".format(NYDUS_CTR_NAME),
        shell=True,
        check=True,
    )


@task
def stop(ctx):
    """
    Remove the Kata developement environment
    """
    result = run(
        "docker rm -f {}".format(NYDUS_CTR_NAME),
        shell=True,
        check=True,
        capture_output=True,
    )
    assert result.returncode == 0


@task
def hot_replace(ctx):
    """
    Replace nydus-image binary from running workon container
    """
    if not is_ctr_running(NYDUS_CTR_NAME):
        print("Must have the work-on container running to hot replace!")
        print("Consider running: inv nydus-snapshotter.cli ")

    print("cp {NYDUS_CTR_NAME}:{NYDUS_IMAGE_CTR_PATH} {NYDUS_IMAGE_HOST_PATH}")
    docker_cmd = (
        f"sudo docker cp {NYDUS_CTR_NAME}:{NYDUS_IMAGE_CTR_PATH} "
        f"{NYDUS_IMAGE_HOST_PATH}"
    )
    result = run(docker_cmd, shell=True, capture_output=True)
    assert result.returncode == 0
