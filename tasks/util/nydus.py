from os import environ
from os.path import dirname, join
from subprocess import run
from tasks.util.docker import build_image
from tasks.util.env import COCO_ROOT, GHCR_URL, GITHUB_ORG, PROJ_ROOT
from tasks.util.versions import NYDUS_VERSION

NYDUSIFY_PATH = join(PROJ_ROOT, "bin", "nydusify")

NYDUS_IMAGE_TAG = join(GHCR_URL, GITHUB_ORG, "nydus") + f":{NYDUS_VERSION}"
NYDUS_IMAGE_HOST_PATH = join(COCO_ROOT, "bin", "nydus-image")


def build_nydus_image(nocache, push, debug=True):
    build_image(
        NYDUS_IMAGE_TAG,
        join(PROJ_ROOT, "docker", "nydus.dockerfile"),
        nocache=nocache,
        push=push,
        debug=debug,
    )


def nydusify(src_tag, dst_tag):
    # Add nydus-image to path
    work_env = environ.copy()
    work_env["PATH"] = work_env.get("PATH", "") + ":" + dirname(NYDUS_IMAGE_HOST_PATH)

    # Note that nydusify automatically pushes the image
    result = run(
        f"{NYDUSIFY_PATH} convert --source {src_tag} --target {dst_tag}",
        shell=True,
        capture_output=True,
        env=work_env,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8").strip()
