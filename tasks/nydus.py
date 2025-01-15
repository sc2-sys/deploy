from invoke import task
from os.path import join
from subprocess import run
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
    docker_cmd = "docker run -td --name {} {} bash".format(
        NYDUS_CTR_NAME, NYDUS_IMAGE_TAG
    )
    result = run(docker_cmd, shell=True, capture_output=True)
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
    if debug:
        print(result.stdout.decode("utf-8").strip())

    def cleanup():
        docker_cmd = "docker rm -f {}".format(NYDUS_CTR_NAME)
        result = run(docker_cmd, shell=True, capture_output=True)
        assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
        if debug:
            print(result.stdout.decode("utf-8").strip())

    base_ctr_dir = "/go/src/github.com/sc2-sys/nydus"
    binaries = [
        {
            "ctr_path": f"{base_ctr_dir}/contrib/nydusify/cmd/nydusify",
            "host_path": NYDUSIFY_PATH,
        }
    ]
    for binary in binaries:
        docker_cmd = "docker cp {}:{} {}".format(
            NYDUS_CTR_NAME, binary["ctr_path"], binary["host_path"]
        )
        result = run(docker_cmd, shell=True, capture_output=True)
        assert result.returncode == 0, (
            cleanup(),
            print(result.stderr.decode("utf-8").strip()),
        )
        if debug:
            print(result.stdout.decode("utf-8").strip())

    cleanup()
