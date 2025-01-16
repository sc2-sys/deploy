from invoke import task
from os.path import join
from subprocess import run
from tasks.util.docker import copy_from_ctr_image
from tasks.util.env import GHCR_URL, GITHUB_ORG, PROJ_ROOT
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


@task
def install(ctx, debug=False, clean=False):
    """
    Install the nydus snapshotter binaries and the nydusify CLI tool
    """
    ctr_bin = ["/go/src/github.com/sc2-sys/nydus/contrib/nydusify/cmd/nydusify"]
    host_bin = [NYDUSIFY_PATH]
    copy_from_ctr_image(NYDUS_IMAGE_TAG, ctr_bin, host_bin, requires_sudo=False)
