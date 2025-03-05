from os import environ, makedirs
from os.path import dirname, exists, join
from subprocess import run
from tasks.util.docker import build_image, copy_from_ctr_image, is_ctr_running
from tasks.util.env import (
    CONTAINERD_CONFIG_FILE,
    GHCR_URL,
    GITHUB_ORG,
    KATA_CONFIG_DIR,
    KATA_IMG_DIR,
    KATA_ROOT,
    KATA_RUNTIMES,
    KATA_WORKON_CTR_NAME,
    PAUSE_IMAGE_REPO,
    PROJ_ROOT,
    SC2_RUNTIMES,
)
from tasks.util.registry import HOST_CERT_PATH
from tasks.util.versions import KATA_VERSION, PAUSE_IMAGE_VERSION, RUST_VERSION
from tasks.util.toml import remove_entry_from_toml, update_toml

KATA_IMAGE_TAG = join(GHCR_URL, GITHUB_ORG, "kata-containers") + f":{KATA_VERSION}"

# These paths are hardcoded in the docker image: ./docker/kata.dockerfile
KATA_SOURCE_DIR = "/go/src/github.com/kata-containers/kata-containers-sc2"
KATA_AGENT_SOURCE_DIR = join(KATA_SOURCE_DIR, "src", "agent")
KATA_SHIM_SOURCE_DIR = join(KATA_SOURCE_DIR, "src", "runtime")
KATA_BASELINE_SOURCE_DIR = "/go/src/github.com/kata-containers/kata-containers-baseline"
KATA_BASELINE_AGENT_SOURCE_DIR = join(KATA_BASELINE_SOURCE_DIR, "src", "agent")
KATA_BASELINE_SHIM_SOURCE_DIR = join(KATA_BASELINE_SOURCE_DIR, "src", "runtime")


def build_kata_image(nocache, push, debug=True):
    build_image(
        KATA_IMAGE_TAG,
        join(PROJ_ROOT, "docker", "kata.dockerfile"),
        build_args={"RUST_VERSION": RUST_VERSION},
        nocache=nocache,
        push=push,
        debug=debug,
    )


def build_pause_image(sc2, debug, hot_replace):
    """
    When we create a rootfs for CoCo, we need to embed the pause image into
    it. As a consequence, we need to build the tarball first.
    """
    pause_image_build_dir = "/tmp/sc2-pause-image-build-dir"

    if exists(pause_image_build_dir):
        run(f"sudo rm -rf {pause_image_build_dir}", shell=True, check=True)

    makedirs(pause_image_build_dir)
    makedirs(join(pause_image_build_dir, "static-build"))
    makedirs(join(pause_image_build_dir, "scripts"))

    script_files = ["static-build/pause-image", "scripts/lib.sh"]
    for ctr_path, host_path in zip(
        [
            join(
                KATA_SOURCE_DIR if sc2 else KATA_BASELINE_SOURCE_DIR,
                "tools/packaging",
                script,
            )
            for script in script_files
        ],
        [join(pause_image_build_dir, script) for script in script_files],
    ):
        copy_from_kata_workon_ctr(
            ctr_path, host_path, sudo=False, debug=debug, hot_replace=hot_replace
        )

    # Build pause image
    work_env = environ.update(
        {
            "pause_image_repo": PAUSE_IMAGE_REPO,
            "pause_image_version": PAUSE_IMAGE_VERSION,
        }
    )
    out = run(
        "./build.sh",
        shell=True,
        cwd=join(pause_image_build_dir, "static-build", "pause-image"),
        env=work_env,
        capture_output=True,
    )
    assert out.returncode == 0, "Error building pause image: {}".format(
        out.stderr.decode("utf-8")
    )

    # Generate tarball of pause bundle
    pause_bundle_tarball_name = "pause_bundle_sc2.tar.xz"
    tar_cmd = f"tar -cJf {pause_bundle_tarball_name} pause_bundle"
    run(
        tar_cmd,
        shell=True,
        check=True,
        cwd=join(pause_image_build_dir, "static-build", "pause-image"),
    )

    return join(
        pause_image_build_dir, "static-build", "pause-image", pause_bundle_tarball_name
    )


def run_kata_workon_ctr(mount_path=None):
    """
    Start Kata workon container image if it is not running. Return `True` if
    we actually did start the container
    """
    if is_ctr_running(KATA_WORKON_CTR_NAME):
        return False

    docker_cmd = [
        "docker run",
        "-d -t",
        (f"-v {mount_path}:{KATA_SOURCE_DIR}" if mount_path else ""),
        "--name {}".format(KATA_WORKON_CTR_NAME),
        KATA_IMAGE_TAG,
        "bash",
    ]
    docker_cmd = " ".join(docker_cmd)
    out = run(docker_cmd, shell=True, capture_output=True)
    assert out.returncode == 0, "Error starting Kata workon ctr: {}".format(
        out.stderr.decode("utf-8")
    )

    return True


def stop_kata_workon_ctr():
    result = run(
        "docker rm -f {}".format(KATA_WORKON_CTR_NAME),
        shell=True,
        check=True,
        capture_output=True,
    )
    assert result.returncode == 0


def copy_from_kata_workon_ctr(
    ctr_path, host_path, sudo=False, debug=False, hot_replace=False
):
    if hot_replace and not is_ctr_running(KATA_WORKON_CTR_NAME):
        print("Must have the work-on container running to hot replace!")
        print("Consider running: inv containerd.cli ")
        raise RuntimeError("Hot-replace without work-on running!")

    if hot_replace:
        # If hot-replacing, manually copy from the work-on image
        docker_cmd = "docker cp {}:{} {}".format(
            KATA_WORKON_CTR_NAME,
            ctr_path,
            host_path,
        )

        if sudo:
            docker_cmd = "sudo {}".format(docker_cmd)
        if debug:
            print(docker_cmd)

        result = run(docker_cmd, shell=True, capture_output=True)
        assert result.returncode == 0, "Error copying from container: {}".format(
            result.stderr.decode("utf-8")
        )
        if debug:
            print(result.stdout.decode("utf-8").strip())
    else:
        # If not hot-replacing, use the built-in method to copy from a
        # container rootfs without initializing it
        copy_from_ctr_image(KATA_IMAGE_TAG, [ctr_path], [host_path], requires_sudo=sudo)


def prepare_rootfs(tmp_rootfs_base_dir, debug=False, sc2=False, hot_replace=False):
    """
    This function takes a directory as input, and generates the root-filesystem
    needed in SC2 at <tmp_rootfs_base_dir>/rootfs. The result can be consumed
    to pack an `initrd`
    """

    # ----- Prepare temporary rootfs directory -----

    tmp_rootfs_dir = join(tmp_rootfs_base_dir, "rootfs")
    tmp_rootfs_scripts_dir = join(tmp_rootfs_base_dir, "osbuilder")

    if exists(tmp_rootfs_base_dir):
        out = run(f"sudo rm -rf {tmp_rootfs_base_dir}", shell=True, capture_output=True)
        assert out.returncode == 0, "Error removing previous rootfs: {}".format(
            out.stderr.decode("utf-8")
        )

    makedirs(tmp_rootfs_base_dir)
    makedirs(tmp_rootfs_dir)
    makedirs(tmp_rootfs_scripts_dir)
    makedirs(join(tmp_rootfs_scripts_dir, "initrd-builder"))
    makedirs(join(tmp_rootfs_scripts_dir, "rootfs-builder"))
    makedirs(join(tmp_rootfs_scripts_dir, "rootfs-builder", "ubuntu"))
    makedirs(join(tmp_rootfs_scripts_dir, "scripts"))

    # Copy all the tooling/script files we need from the container
    script_files = [
        "initrd-builder/initrd_builder.sh",
        "rootfs-builder/rootfs.sh",
        "rootfs-builder/nvidia",
        "rootfs-builder/ubuntu/config.sh",
        "rootfs-builder/ubuntu/Dockerfile.in",
        "rootfs-builder/ubuntu/rootfs_lib.sh",
        "scripts/lib.sh",
    ]

    for ctr_path, host_path in zip(
        [
            join(
                KATA_SOURCE_DIR if sc2 else KATA_BASELINE_SOURCE_DIR,
                "tools/osbuilder",
                script,
            )
            for script in script_files
        ],
        [join(tmp_rootfs_scripts_dir, script) for script in script_files],
    ):
        copy_from_kata_workon_ctr(
            ctr_path, host_path, sudo=True, debug=debug, hot_replace=hot_replace
        )

    # Also copy a policy file needed to build the rootfs
    copy_from_kata_workon_ctr(
        join(
            KATA_SOURCE_DIR if sc2 else KATA_BASELINE_SOURCE_DIR,
            "src/kata-opa/allow-all.rego",
        ),
        join(tmp_rootfs_base_dir, "allow-all.rego"),
        sudo=True,
        debug=debug,
        hot_replace=hot_replace,
    )

    # Finally, also copy our kata agent
    agent_host_path = join(
        KATA_AGENT_SOURCE_DIR if sc2 else KATA_BASELINE_AGENT_SOURCE_DIR,
        "target",
        "x86_64-unknown-linux-musl",
        "release",
        "kata-agent",
    )
    copy_from_kata_workon_ctr(
        agent_host_path,
        join(tmp_rootfs_base_dir, "kata-agent"),
        sudo=True,
        debug=debug,
        hot_replace=hot_replace,
    )

    # ----- Populate rootfs with base ubuntu using Kata's scripts -----

    out = run(
        "sudo DEBIAN_FRONTEND=noninteractive apt install -y makedev multistrap",
        shell=True,
        capture_output=True,
    )
    assert out.returncode == 0, "Error preparing rootfs: {}".format(
        out.stderr.decode("utf-8")
    )

    rootfs_builder_dir = join(tmp_rootfs_scripts_dir, "rootfs-builder")
    work_env = {
        "AGENT_INIT": "yes",
        "AGENT_POLICY_FILE": join(tmp_rootfs_base_dir, "allow-all.rego"),
        "AGENT_SOURCE_BIN": join(tmp_rootfs_base_dir, "kata-agent"),
        "CONFIDENTIAL_GUEST": "yes",
        "DMVERITY_SUPPORT": "yes",
        "MEASURED_ROOTFS": "no",
        # We build the `initrd` inside a container image to prevent different
        # host OS versions from introducing subtle changes in the rootfs
        "USE_DOCKER": "yes",
        "OS_VERSION": "jammy",
        "RUST_VERSION": "1.75.0",
        "GO_VERSION": "1.22.2",
        "PAUSE_IMAGE_TARBALL": build_pause_image(
            sc2=sc2, debug=debug, hot_replace=hot_replace
        ),
        "PULL_TYPE": "default",
        "ROOTFS_DIR": tmp_rootfs_dir,
    }
    rootfs_builder_cmd = f"sudo -E {rootfs_builder_dir}/rootfs.sh ubuntu"
    out = run(
        rootfs_builder_cmd,
        shell=True,
        env=work_env,
        cwd=rootfs_builder_dir,
        capture_output=True,
    )
    assert out.returncode == 0, "Error preparing rootfs: {}".format(
        out.stderr.decode("utf-8")
    )
    if debug:
        print(out.stdout.decode("utf-8").strip())

    # ----- Add extra files to the rootfs -----

    extra_files = {
        "/etc/hosts": {"path": "/etc/hosts", "mode": "w"},
        HOST_CERT_PATH: {"path": "/etc/ssl/certs/ca-certificates.crt", "mode": "a"},
    }

    # Include any extra files that the caller may have provided
    if extra_files is not None:
        for host_path in extra_files:
            # Trim any absolute paths expressed as "guest" paths to be able to
            # append the rootfs
            rel_guest_path = extra_files[host_path]["path"]
            if rel_guest_path.startswith("/"):
                rel_guest_path = rel_guest_path[1:]

            guest_path = join(tmp_rootfs_dir, rel_guest_path)
            if not exists(dirname(guest_path)):
                run(
                    "sudo mkdir -p {}".format(dirname(guest_path)),
                    shell=True,
                    check=True,
                )

            if exists(guest_path) and extra_files[host_path]["mode"] == "a":
                run(
                    'sudo sh -c "cat {} >> {}"'.format(host_path, guest_path),
                    shell=True,
                    check=True,
                )
            else:
                run(
                    "sudo cp {} {}".format(host_path, guest_path),
                    shell=True,
                    check=True,
                )


def replace_agent(
    dst_initrd_path=join(KATA_IMG_DIR, "kata-containers-initrd-confidential-sc2.img"),
    debug=False,
    sc2=False,
    hot_replace=False,
):
    """
    Replace the kata-agent with a custom-built one

    We use Kata's `rootfs-builder` to prepare a `rootfs` based on an Ubuntu
    image with custom packages, then copy into the rootfs additional files
    that we may need, and finally package it using Kata's `initrd-builder`.
    """
    # Generate rootfs
    tmp_rootfs_base_dir = "/tmp/sc2-rootfs-build-dir"
    tmp_rootfs_dir = join(tmp_rootfs_base_dir, "rootfs")
    tmp_rootfs_scripts_dir = join(tmp_rootfs_base_dir, "osbuilder")
    prepare_rootfs(tmp_rootfs_base_dir, debug=debug, sc2=sc2, hot_replace=hot_replace)

    # ----- Pack rootfs into initrd using Kata's script -----

    work_env = {"AGENT_INIT": "yes"}
    initrd_pack_cmd = "sudo -E {} -o {} {}".format(
        join(tmp_rootfs_scripts_dir, "initrd-builder", "initrd_builder.sh"),
        dst_initrd_path,
        tmp_rootfs_dir,
    )
    out = run(initrd_pack_cmd, shell=True, env=work_env, capture_output=True)
    assert out.returncode == 0, "Error packing initrd: {}".format(
        out.stderr.decode("utf-8")
    )
    if debug:
        print(out.stdout.decode("utf-8").strip())

    # Lastly, update the Kata config to point to the new initrd
    target_runtimes = SC2_RUNTIMES if sc2 else KATA_RUNTIMES
    for runtime in target_runtimes:
        # QEMU uses an optimized image file (no initrd) so we keep it that way
        # also, for the time being, the QEMU baseline requires no patches
        if runtime == "qemu":
            continue

        conf_file_path = join(KATA_CONFIG_DIR, "configuration-{}.toml".format(runtime))
        updated_toml_str = """
        [hypervisor.qemu]
        initrd = "{new_initrd_path}"
        """.format(
            new_initrd_path=dst_initrd_path
        )
        update_toml(conf_file_path, updated_toml_str)

        if runtime == "qemu-coco-dev" or "tdx" in runtime:
            remove_entry_from_toml(conf_file_path, "hypervisor.qemu.image")


def replace_shim(
    dst_shim_binary=join(KATA_ROOT, "bin", "containerd-shim-kata-sc2-v2"),
    dst_runtime_binary=join(KATA_ROOT, "bin", "kata-runtime-sc2"),
    sc2=True,
    hot_replace=False,
):
    """
    Replace the containerd-kata-shim with a custom one

    To replace the agent, we just need to change the soft-link from the right
    shim to our re-built one
    """
    # First, copy the binary from the source tree
    src_shim_binary = join(
        KATA_SHIM_SOURCE_DIR if sc2 else KATA_BASELINE_SHIM_SOURCE_DIR,
        "containerd-shim-kata-v2",
    )
    copy_from_kata_workon_ctr(
        src_shim_binary, dst_shim_binary, sudo=True, hot_replace=hot_replace
    )

    # Also copy the kata-runtime binary
    src_runtime_binary = join(
        KATA_SHIM_SOURCE_DIR if sc2 else KATA_BASELINE_SHIM_SOURCE_DIR,
        "kata-runtime",
    )
    copy_from_kata_workon_ctr(
        src_runtime_binary, dst_runtime_binary, sudo=True, hot_replace=hot_replace
    )

    target_runtimes = SC2_RUNTIMES if sc2 else KATA_RUNTIMES
    for runtime in target_runtimes:
        updated_toml_str = """
        [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.kata-{runtime_name}]
        runtime_type = "io.containerd.kata-{runtime_name}.v2"
        runtime_path = "{ctrd_path}"
        """.format(
            runtime_name=runtime, ctrd_path=dst_shim_binary
        )
        update_toml(CONTAINERD_CONFIG_FILE, updated_toml_str)
