from invoke import task
from os.path import exists, join
from shutil import rmtree
from subprocess import run
from tasks.util.env import GHCR_URL, GITHUB_ORG
from tasks.util.trustee import (
    KBS_CONFIG_DIR,
    KBS_HOST_PORT,
    TRUSTEE_DIR,
    SIGNATURE_POLICY_NONE,
    clear_kbs_db,
    get_kbs_db_ip,
    provision_launch_digest as do_provision_launch_digest,
)

SIMPLE_KBS_SERVER_IMAGE_NAME = join(GHCR_URL, GITHUB_ORG, "simple-kbs-server:latest")
TRUSTEE_COMPOSE_ENV = {"KBS_HOST_PORT": KBS_HOST_PORT}


def check_trustee_dir():
    # TODO: think about how to deploy the trustee
    if not exists(TRUSTEE_DIR):
        print(f"ERROR: could not find local Trustee checkout at {TRUSTEE_DIR}")
        exit(1)

    """
    target_dir = join(TRUSTEE_DIR, "target")
    if not exists(target_dir):
        print("Populating {} with the pre-compiled binaries...".format(target_dir))
        tmp_ctr_name = "simple-kbs-workon"
        docker_cmd = "docker run -d --entrypoint bash --name {} {}".format(
            tmp_ctr_name, SIMPLE_KBS_SERVER_IMAGE_NAME
        )
        run(docker_cmd, shell=True, check=True)

        cp_cmd = "docker cp {}:/usr/src/simple-kbs/target {}".format(
            tmp_ctr_name, target_dir
        )
        run(cp_cmd, shell=True, check=True)

        run("docker rm -f {}".format(tmp_ctr_name), shell=True, check=True)
    """


def do_start(debug=False, clean=False):
    check_trustee_dir()

    if clean and exists(KBS_CONFIG_DIR):
        rmtree(KBS_CONFIG_DIR)

    # First, generate a priave key for the kbs
    priv_key = join(KBS_CONFIG_DIR, "private.key")
    pub_key = join(KBS_CONFIG_DIR, "public.pub")
    openssl_cmd = f"openssl genpkey -algorithm ed25519 > {priv_key}"
    result = run(openssl_cmd, shell=True, capture_output=True)
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
    if debug:
        print(result.stdout.decode("utf-8").strip())

    openssl_cmd = f"openssl pkey -in {priv_key} -pubout -out {pub_key}"
    result = run(openssl_cmd, shell=True, capture_output=True)
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
    if debug:
        print(result.stdout.decode("utf-8").strip())

    # Now just start the trustee services
    result = run("docker compose up -d", shell=True, capture_output=True, cwd=TRUSTEE_DIR, env=TRUSTEE_COMPOSE_ENV)
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
    if debug:
        print(result.stdout.decode("utf-8").strip())


@task
def start(ctx, debug=False, clean=False):
    """
    Start the simple KBS service
    """
    do_start(debug=debug, clean=clean)


@task
def stop(ctx, debug=False):
    """
    Stop the simple KBS service
    """
    check_trustee_dir()
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


@task
def clear_db(ctx, skip_secrets=False):
    """
    Clear the contents of the KBS DB
    """
    clear_kbs_db(skip_secrets=skip_secrets)


@task
def get_db_ip(ctx):
    print(get_kbs_db_ip())


@task
def provision_launch_digest(ctx, signature_policy=SIGNATURE_POLICY_NONE, clean=False):
    """
    Provision the KBS with the launch digest for the current node

    In order to make the Kata Agent validate the FW launch digest measurement
    we need to enable signature verification. Signature verification has an
    associated resource that contains the verification policy. By associating
    this resource to a launch digest policy (beware of the `policy` term
    overloading, but these are KBS terms), we force the Kata Agent to also
    enforce the launch digest policy.

    We support different kinds of signature verification policies, and only
    one kind of launch digest policy.

    For signature verification, we have:
    - the NONE policy, that accepts all images
    - the VERIFY policy, that verifies all (unencrypted) images

    For launch digest, we manually generate the measure digest, and include it
    in the policy. If the FW digest is not exactly the one in the policy, boot
    fails.
    """
    # For the purposes of the demo, we hardcode the images we include in the
    # policy to be included in the signature policy
    images_to_sign = [
        f"docker.io/{GITHUB_ORG}/coco-helloworld-py",
        f"docker.io/{GITHUB_ORG}/coco-knative-sidecar",
        f"ghcr.io/{GITHUB_ORG}/coco-helloworld-py",
        f"ghcr.io/{GITHUB_ORG}/coco-knative-sidecar",
        f"registry.coco-csg.com/{GITHUB_ORG}/coco-helloworld-py",
        f"registry.coco-csg.com/{GITHUB_ORG}/coco-knative-sidecar",
    ]

    do_provision_launch_digest(
        images_to_sign, signature_policy=signature_policy, clean=clean
    )
