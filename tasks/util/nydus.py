from os import environ
from os.path import dirname, join
from subprocess import run
from tasks.util.env import COCO_ROOT, PROJ_ROOT

NYDUSIFY_PATH = join(PROJ_ROOT, "bin", "nydusify")

NYDUS_IMAGE_HOST_PATH = join(COCO_ROOT, "bin", "nydus-image")


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
