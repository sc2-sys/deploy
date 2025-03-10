from invoke import task
from os.path import join
from tasks.util.docker import copy_from_ctr_image
from tasks.util.env import KATA_ROOT
from tasks.util.ovmf import OVMF_IMAGE_TAG, build_ovmf_image


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
    build_ovmf_image(nocache, push)
