from invoke import task
from os.path import join
from tasks.svsm import build_svsm_image, build_svsm_kernel_image, build_svsm_qemu_image
from tasks.util.containerd import build_containerd_image
from tasks.util.docker import BASE_IMAGE_TAG, build_image
from tasks.util.env import PROJ_ROOT, print_dotted_line
from tasks.util.kata import build_kata_image
from tasks.util.nydus import build_nydus_image
from tasks.util.nydus_snapshotter import build_nydus_snapshotter_image
from tasks.util.ovmf import build_ovmf_image
from tasks.util.versions import (
    CONTAINERD_VERSION,
    GO_VERSION,
    KATA_VERSION,
    NYDUS_VERSION,
    NYDUS_SNAPSHOTTER_VERSION,
    OVMF_VERSION,
)


def build_base_image(nocache, push, debug=True):
    build_image(
        BASE_IMAGE_TAG,
        join(PROJ_ROOT, "docker", "base.dockerfile"),
        build_args={"GO_VERSION": GO_VERSION},
        nocache=nocache,
        push=push,
        debug=debug,
    )


@task
def build_base(ctx, nocache=False, push=False):
    """
    Build base docker container
    """
    build_base_image(nocache, push)


@task
def build_all(ctx, nocache=False, push=False):
    """
    Build all work-on container images
    """
    print_dotted_line("Building base image")
    build_base_image(nocache, push, debug=False)
    print("Success!")

    print_dotted_line(f"Building containerd image (v{CONTAINERD_VERSION})")
    build_containerd_image(nocache, push, debug=False)
    print("Success!")

    print_dotted_line(f"Building kata image (v{KATA_VERSION})")
    build_kata_image(nocache, push, debug=False)
    print("Success!")

    print_dotted_line(f"Building nydus image (v{NYDUS_VERSION})")
    build_nydus_image(nocache, push, debug=False)
    print("Success!")

    print_dotted_line(
        f"Building nydus-snapshotter image (v{NYDUS_SNAPSHOTTER_VERSION})"
    )
    build_nydus_snapshotter_image(nocache, push, debug=False)
    print("Success!")

    print_dotted_line(f"Building OVMF image (v{OVMF_VERSION})")
    build_ovmf_image(nocache, push, debug=False)
    print("Success!")

    print_dotted_line("Building SVSM guest kernel image")
    build_svsm_kernel_image(nocache, push, debug=False)
    print("Success!")

    print_dotted_line("Building SVSM QEMU image")
    build_svsm_qemu_image(nocache, push, debug=False)
    print("Success!")

    # This must be after SVSM's qemu and kernel
    print_dotted_line("Building SVSM IGVM image")
    build_svsm_image(nocache, push, debug=False)
    print("Success!")
