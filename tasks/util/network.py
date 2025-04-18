from os.path import exists, join
from os import makedirs
from subprocess import run
from tasks.util.env import BIN_DIR, GLOBAL_BIN_DIR

import os
import tempfile


def download_binary(url, binary_name, debug=False):
    """
    Fetch a Kubernetes binary by downloading into a temporary file in BIN_DIR,
    making it executable, and then atomically replacing any existing binary.
    Returns the full path to the downloaded binary.
    """
    # Ensure the target directory exists
    os.makedirs(BIN_DIR, exist_ok=True)

    # Create a secure temp file in the same directory
    fd, tmp_path = tempfile.mkstemp(prefix=binary_name, dir=BIN_DIR)
    os.close(fd)

    # Download directly into the temp file
    cmd = f"curl -L -o {tmp_path} {url}"
    result = run(cmd, shell=True, capture_output=True)
    if result.returncode != 0:
        err = result.stderr.decode().strip()
        raise RuntimeError(f"Failed to download {binary_name} from {url}: {err}")
    if debug:
        print(result.stdout.decode().strip())

    # Make the downloaded file executable
    os.chmod(tmp_path, 0o755)

    # Atomically move it into place, replacing any existing binary
    dest_path = join(BIN_DIR, binary_name)
    os.replace(tmp_path, dest_path)

    if debug:
        print(f"[DEBUG] Placed {binary_name} at {dest_path}")

    return dest_path


def symlink_global_bin(binary_path, name, debug=False):
    global_path = join(GLOBAL_BIN_DIR, name)
    if exists(global_path):
        if debug:
            print("Removing existing binary at {}".format(global_path))
        run(
            "sudo rm -f {}".format(global_path),
            shell=True,
            check=True,
        )

    if debug:
        print("Symlinking {} -> {}".format(global_path, binary_path))
    run(
        "sudo ln -sf {} {}".format(binary_path, name),
        shell=True,
        check=True,
        cwd=GLOBAL_BIN_DIR,
    )
