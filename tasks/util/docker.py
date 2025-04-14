from os.path import dirname, exists, join
from subprocess import run
from tasks.util.env import GHCR_URL, GITHUB_ORG, PROJ_ROOT, print_dotted_line
from tasks.util.versions import (
    CONTAINERD_VERSION,
    KATA_VERSION,
    NYDUS_SNAPSHOTTER_VERSION,
    NYDUS_VERSION,
    OVMF_VERSION,
)

# Base software image (note that we tag with a CoCo release version, but we
# allow it to fall behind as we should not re-build the base image often)
BASE_IMAGE_TAG = join(GHCR_URL, GITHUB_ORG, "base") + ":0.12.0"

ALL_CTR_IMAGES = [
    (join(GHCR_URL, GITHUB_ORG, f"kata-containers:{KATA_VERSION}"), "kata.dockerfile"),
    (join(GHCR_URL, GITHUB_ORG, f"nydus:{NYDUS_VERSION}"), "nydus.dockerfile"),
    (
        join(GHCR_URL, GITHUB_ORG, f"nydus-snapshotter:{NYDUS_SNAPSHOTTER_VERSION}"),
        "nydus_snapshotter.dockerfile",
    ),
    (join(GHCR_URL, GITHUB_ORG, f"ovmf:{OVMF_VERSION}"), "ovmf.dockerfile"),
    (join(GHCR_URL, GITHUB_ORG, "svsm:main"), "svsm.dockerfile"),
    # (join(GHCR_URL, GITHUB_ORG, "linux:svsm"), "svsm_kernel.dockerfile"),
    (join(GHCR_URL, GITHUB_ORG, "qemu:svsm"), "svsm_qemu.dockerfile"),
]


def build_image(
    image_tag,
    dockerfile,
    build_args=None,
    cwd=PROJ_ROOT,
    nocache=False,
    push=False,
    debug=False,
):
    build_args_cmd = ""
    if build_args:
        build_args_cmd = " ".join(
            [
                "--build-arg {}={}".format(key, value)
                for key, value in build_args.items()
            ]
        )
    docker_cmd = "docker build {} {} -t {} -f {} .".format(
        "--no-cache" if nocache else "", build_args_cmd, image_tag, dockerfile
    )
    result = run(docker_cmd, shell=True, capture_output=True, cwd=cwd)
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
    if debug:
        print(result.stdout.decode("utf-8").strip())

    if push:
        result = run(f"docker push {image_tag}", shell=True, capture_output=True)
        assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
        if debug:
            print(result.stdout.decode("utf-8").strip())


def copy_from_ctr_image(ctr_image, ctr_paths, host_paths, requires_sudo=False):
    """
    Copy from a container image without actually running the container
    """
    tmp_ctr_name = "tmp-build-ctr"
    result = run(
        f"docker create --name {tmp_ctr_name} {ctr_image}",
        shell=True,
        capture_output=True,
    )
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())

    def cleanup():
        result = run(f"docker rm -f {tmp_ctr_name}", shell=True, capture_output=True)
        assert result.returncode == 0

    for ctr_path, host_path in zip(ctr_paths, host_paths):
        host_dir = dirname(host_path)
        if not exists(host_dir):
            mkdir = "sudo mkdir" if requires_sudo else "mkdir"
            result = run(f"{mkdir} -p {host_dir}", shell=True, capture_output=True)
            assert result.returncode == 0

        try:
            prefix = "sudo " if requires_sudo else ""
            result = run(
                f"{prefix}docker cp {tmp_ctr_name}:{ctr_path} {host_path}",
                shell=True,
                capture_output=True,
            )
            assert result.returncode == 0
        except AssertionError:
            stderr = result.stderr.decode("utf-8").strip()
            print(f"Error copying {ctr_image}:{ctr_path} to {host_path}: {stderr}")
            cleanup()
            raise RuntimeError("Error copying from container!")

    cleanup()


def is_ctr_running(ctr_name):
    """
    Work out whether a container is running or not
    """
    docker_cmd = ["docker container inspect", "-f '{{.State.Running}}'", ctr_name]
    docker_cmd = " ".join(docker_cmd)
    out = run(docker_cmd, shell=True, capture_output=True)
    if out.returncode == 0:
        value = out.stdout.decode("utf-8").strip()
        return value == "true"

    return False


def pull_artifact_images(debug=False):
    print_dotted_line("Pulling artifact container images")
    components = ["containerd", "kata-containers", "nydus", "nydus-snapshotter", "ovmf"]
    versions = [
        CONTAINERD_VERSION,
        KATA_VERSION,
        NYDUS_VERSION,
        NYDUS_SNAPSHOTTER_VERSION,
        OVMF_VERSION,
    ]
    for component, version in zip(components, versions):
        docker_cmd = f"docker pull {GHCR_URL}/{GITHUB_ORG}/{component}:{version}"
        result = run(docker_cmd, shell=True, capture_output=True)
        assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
        if debug:
            print(result.stdout.decode("utf-8").strip())

    print("Success!")    
