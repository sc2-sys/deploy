from os.path import join
from tasks.util.env import GHCR_URL, GITHUB_ORG, PROJ_ROOT
from tasks.util.docker import build_image
from tasks.util.versions import NYDUS_SNAPSHOTTER_VERSION

NYDUS_SNAPSHOTTER_IMAGE_TAG = (
    join(GHCR_URL, GITHUB_ORG, "nydus-snapshotter") + f":{NYDUS_SNAPSHOTTER_VERSION}"
)


def build_nydus_snapshotter_image(nocache, push, debug=True):
    build_image(
        NYDUS_SNAPSHOTTER_IMAGE_TAG,
        join(PROJ_ROOT, "docker", "nydus_snapshotter.dockerfile"),
        nocache=nocache,
        push=push,
        debug=debug,
    )
