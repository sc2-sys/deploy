from invoke import task
from os import makedirs
from os.path import exists, join
from subprocess import run
from tasks.util.cosign import install as cosign_install, sign_container_image
from tasks.util.docker import build_image, copy_from_ctr_image
from tasks.util.env import GHCR_URL, GITHUB_ORG, PROJ_ROOT
from tasks.util.trustee import (
    TRUSTEE_HOST_CONFIG_DIR,
    TRUSTEE_KBS_HOST_PORT,
    TRUSTEE_DIR,
    do_set_guest_attestation_mode,
)

TRUSTEE_IMAGE_TAG = join(GHCR_URL, GITHUB_ORG, "trustee:main")

TRUSTEE_HOST_BIN_MOUNT_DIR = join(TRUSTEE_DIR, "target", "release")
TRUSTEE_GUEST_BIN_MOUNT_DIR = "/git/sc2-sys/trustee/target/release"

TRUSTEE_COMPOSE_ENV = {
    "KBS_HOST_PORT": TRUSTEE_KBS_HOST_PORT,
    "TRUSTEE_HOST_BIN_MOUNT_DIR": TRUSTEE_HOST_BIN_MOUNT_DIR,
    "TRUSTEE_GUEST_BIN_MOUNT_DIR": TRUSTEE_GUEST_BIN_MOUNT_DIR,
    "TRUSTEE_HOST_CONFIG_DIR": TRUSTEE_HOST_CONFIG_DIR,
}


def build_trustee_image(nocache, push, debug=True):
    build_image(
        TRUSTEE_IMAGE_TAG,
        join(PROJ_ROOT, "docker", "trustee.dockerfile"),
        nocache=nocache,
        push=push,
        debug=debug,
    )


def do_start(debug=False, clean=False):
    populate_trustee_bin_mounts(clean)
    populate_trustee_config_mounts(clean)

    result = run(
        "docker compose up -d",
        shell=True,
        capture_output=True,
        cwd=TRUSTEE_DIR,
        env=TRUSTEE_COMPOSE_ENV,
    )
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
    if debug:
        print(result.stdout.decode("utf-8").strip())


def populate_trustee_bin_mounts(clean):
    """
    This method makes sure that we populate the host environment with the
    pre-built binaries in the container images
    """
    if clean:
        result = run(
            f"sudo rm -rf {TRUSTEE_HOST_BIN_MOUNT_DIR}", shell=True, capture_output=True
        )
        assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())

    if exists(TRUSTEE_HOST_BIN_MOUNT_DIR):
        return

    copy_from_ctr_image(
        TRUSTEE_IMAGE_TAG, [TRUSTEE_GUEST_BIN_MOUNT_DIR], [TRUSTEE_HOST_BIN_MOUNT_DIR]
    )


def populate_trustee_config_mounts(clean):
    """
    This method makes sure that we populate the host environment with the
    pre-built binaries in the container images
    """
    if clean:
        result = run(
            f"sudo rm -rf {TRUSTEE_HOST_CONFIG_DIR}", shell=True, capture_output=True
        )
        assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())

    if exists(TRUSTEE_HOST_CONFIG_DIR):
        return

    makedirs(TRUSTEE_HOST_CONFIG_DIR)

    # Generate key-pair for the deployment
    priv_key = join(TRUSTEE_HOST_CONFIG_DIR, "private.key")
    pub_key = join(TRUSTEE_HOST_CONFIG_DIR, "public.pub")
    openssl_cmd = f"openssl genpkey -algorithm ed25519 > {priv_key}"
    result = run(openssl_cmd, shell=True, capture_output=True)
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())

    openssl_cmd = f"openssl pkey -in {priv_key} -pubout -out {pub_key}"
    result = run(openssl_cmd, shell=True, capture_output=True)
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())


# ------------------------------------------------------------------------------
# Main entrypoint tasks
# ------------------------------------------------------------------------------


@task
def build(ctx, nocache=False, push=False):
    """
    Build the Trustee fork for SC2
    """
    build_trustee_image(nocache=nocache, push=push)


@task
def start(ctx, debug=False, clean=False):
    """
    Start the Trustee cluster
    """
    do_start(debug=debug, clean=clean)


@task
def set_guest_attestation_mode(ctx, mode, runtime="qemu-snp-sc2"):
    """
    Set guest attestation mode: [on,off]

    This can also be set using a pod annotation.
    """
    do_set_guest_attestation_mode(mode, runtime)


@task
def stop(ctx, debug=False):
    """
    Stop the Trustee cluster
    """
    result = run(
        "docker compose down",
        shell=True,
        capture_output=True,
        cwd=TRUSTEE_DIR,
        env=TRUSTEE_COMPOSE_ENV,
    )
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
    if debug:
        print(result.stdout.decode("utf-8").strip())
