from invoke import task
from os.path import join
from subprocess import run
from tasks.util.docker import copy_from_ctr_image
from tasks.util.env import COCO_ROOT, GHCR_URL, GITHUB_ORG, PROJ_ROOT, print_dotted_line
from tasks.util.nydus import NYDUSIFY_PATH
from tasks.util.versions import NYDUS_VERSION

NYDUS_CTR_NAME = "nydus-workon"
NYDUS_IMAGE_TAG = join(GHCR_URL, GITHUB_ORG, "nydus") + f":{NYDUS_VERSION}"


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
    ctr_bin = ["/go/src/github.com/sc2-sys/nydus/target/release/nydus-image"]
    host_bin = [join(COCO_ROOT, "bin", "nydus-image")]
    copy_from_ctr_image(NYDUS_IMAGE_TAG, ctr_bin, host_bin, requires_sudo=True)

    print("Success!")


@task
def install(ctx):
    """
    Install the nydusify CLI tool
    """
    do_install()
