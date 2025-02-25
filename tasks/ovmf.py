from invoke import task
from os.path import join
from subprocess import run
from tasks.util.docker import copy_from_ctr_image
from tasks.util.env import GHCR_URL, GITHUB_ORG, KATA_ROOT, PROJ_ROOT
from tasks.util.versions import OVMF_VERSION

OVMF_IMAGE_TAG = join(GHCR_URL, GITHUB_ORG, f"ovmf:{OVMF_VERSION}")


def do_ovmf_build(nocache=False, push=False):
    docker_cmd = [
        "docker build",
        f"--build-arg OVMF_VERSION={OVMF_VERSION}",
        f"-t {OVMF_IMAGE_TAG}",
        "--nocache" if nocache else "",
        "-f {} .".format(join(PROJ_ROOT, "docker", "ovmf.dockerfile")),
    ]
    docker_cmd = " ".join(docker_cmd)
    result = run(docker_cmd, shell=True, check=True, cwd=PROJ_ROOT)
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())

    if push:
        result = run(f"docker push {OVMF_IMAGE_TAG}", shell=True, capture_output=True)
        assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())


def install():
    """
    Copy a custom build of OVMF into the destination path
    """
    ctr_paths = ["/git/sc2-sys/edk2/Build/AmdSev/RELEASE_GCC5/FV/OVMF.fd"]
    host_paths = [join(KATA_ROOT, "share", "ovmf", "AMDSEV.fd")]
    copy_from_ctr_image(OVMF_IMAGE_TAG, ctr_paths, host_paths, requires_sudo=True)


@task
def build(ctx, nocache=False, push=False):
    """
    Build the OVMF work-on container image
    """
    do_ovmf_build(nocache=nocache, push=push)
