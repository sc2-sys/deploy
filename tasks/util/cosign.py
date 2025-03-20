from os.path import exists, join
from subprocess import run
from tasks.util.env import BIN_DIR, K8S_CONFIG_DIR, print_dotted_line
from tasks.util.versions import COSIGN_VERSION
from tasks.util.trustee import TRUSTEE_HOST_CONFIG_DIR

COSIGN_BINARY = join(BIN_DIR, "cosign")

COSIGN_PASSWORD = "foobar123"
COSIGN_PRIV_KEY = join(TRUSTEE_HOST_CONFIG_DIR, "cosign.key")
COSIGN_PUB_KEY = join(TRUSTEE_HOST_CONFIG_DIR, "cosign.pub")


def install(debug):
    """
    Install the cosign tool to sign container images
    """
    print_dotted_line(f"Installing cosign (v{COSIGN_VERSION})")
    cosign_url = "https://github.com/sigstore/cosign/releases/download/"
    cosign_url += "v{}/cosign-linux-amd64".format(COSIGN_VERSION)
    cosign_path = join(BIN_DIR, COSIGN_BINARY)
    result = run(
        "wget {} -O {}".format(cosign_url, cosign_path), shell=True, capture_output=True
    )
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
    if debug:
        print(result.stdout.decode("utf-8").strip())

    result = run("chmod +x {}".format(cosign_path), shell=True, capture_output=True)
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
    if debug:
        print(result.stdout.decode("utf-8").strip())

    print("Success!")


def generate_cosign_keypair():
    """
    Generate the keypair used to sign container images
    """
    result = run(
        f"{BIN_DIR}/cosign generate-key-pair",
        shell=True,
        capture_output=True,
        cwd=TRUSTEE_HOST_CONFIG_DIR,
        env={"COSIGN_PASSWORD": COSIGN_PASSWORD},
    )
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())


def sign_container_image(image_tag):
    if not exists(COSIGN_PUB_KEY):
        generate_cosign_keypair()

    # Actually sign the image
    sign_cmd = (
        f"{COSIGN_BINARY} sign --allow-insecure-registry --yes --key {COSIGN_PRIV_KEY} "
        f"{image_tag}"
    )
    result = run(
        sign_cmd,
        shell=True,
        capture_output=True,
        env={"COSIGN_PASSWORD": COSIGN_PASSWORD},
    )
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
