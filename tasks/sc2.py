from invoke import task
from os import environ, makedirs
from os.path import exists, join
from subprocess import run
from tasks.containerd import (
    install as containerd_install,
    set_log_level as containerd_set_log_level,
)
from tasks.demo_apps import (
    do_push_to_local_registry as push_demo_apps_to_local_registry,
)
from tasks.k8s import install as k8s_tooling_install
from tasks.k9s import install as k9s_install
from tasks.kata import set_log_level as kata_set_log_level
from tasks.kernel import build_guest as build_guest_kernel
from tasks.knative import install as knative_install
from tasks.kubeadm import create as k8s_create, destroy as k8s_destroy
from tasks.nydus_snapshotter import (
    install as nydus_snapshotter_install,
    set_log_level as nydus_snapshotter_set_log_level,
)
from tasks.nydus import do_install as nydus_install
from tasks.operator import (
    install as operator_install,
    install_cc_runtime as operator_install_cc_runtime,
)
from tasks.util.containerd import restart_containerd
from tasks.util.env import (
    COCO_ROOT,
    CONF_FILES_DIR,
    CONTAINERD_CONFIG_FILE,
    CONTAINERD_CONFIG_ROOT,
    KATA_CONFIG_DIR,
    KATA_ROOT,
    KATA_IMAGE_TAG,
    KATA_IMG_DIR,
    PROJ_ROOT,
    SC2_CONFIG_DIR,
    SC2_DEPLOYMENT_FILE,
    SC2_RUNTIMES,
    VM_CACHE_SIZE,
    print_dotted_line,
)
from tasks.util.kata import (
    replace_agent as replace_kata_agent,
    replace_shim as replace_kata_shim,
)
from tasks.util.kubeadm import run_kubectl_command
from tasks.util.registry import (
    HOST_CERT_DIR,
    start as start_local_registry,
    stop as stop_local_registry,
)
from tasks.util.toml import update_toml
from tasks.util.versions import COCO_VERSION, GUEST_KERNEL_VERSION, KATA_VERSION
from time import sleep


def start_vm_cache(debug=False):
    vm_cache_dir = join(PROJ_ROOT, "vm-cache")

    # Build the VM cache server
    if debug:
        print("Building VM cache wrapper...")
    result = run(
        "cargo build --release", cwd=vm_cache_dir, shell=True, capture_output=True
    )
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
    if debug:
        print(result.stdout.decode("utf-8").strip())

    # Run the VM cache server in the background
    if debug:
        print("Running VM cache wrapper in background mode...")
    run(
        "sudo -E target/release/vm-cache background > /dev/null 2>&1",
        cwd=vm_cache_dir,
        env=environ,
        shell=True,
        check=True,
    )


def install_sc2_runtime(debug=False):
    """
    This script installs SC2 as a different runtime class
    """
    # Copy containerd shim (and patch if needed)
    src_ctrd_path = f"{KATA_ROOT}/bin/containerd-shim-kata-v2"
    dst_ctrd_path = f"{KATA_ROOT}/bin/containerd-shim-kata-sc2-v2"
    run(f"sudo cp {src_ctrd_path} {dst_ctrd_path}", shell=True, check=True)

    # Modify containerd to add a new runtime class
    if debug:
        print("Patching containerd...")
    for sc2_runtime in SC2_RUNTIMES:
        # Update containerd to point the SC2 runtime to the right shim
        updated_toml_str = """
        [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.kata-{runtime_name}]
        runtime_type = "io.containerd.kata-{runtime_name}.v2"
        privileged_without_host_devices = true
        pod_annotations = [ "io.katacontainers.*",]
        snapshotter = "nydus"
        runtime_path = "{ctrd_path}"
        """.format(
            runtime_name=sc2_runtime, ctrd_path=dst_ctrd_path
        )
        update_toml(CONTAINERD_CONFIG_FILE, updated_toml_str)

    # Copy configuration file from the corresponding source file (and patch
    # if needed)
    if debug:
        print("Patching configuration files...")
    for sc2_runtime in SC2_RUNTIMES:
        if "snp" in sc2_runtime:
            src_conf_path = join(KATA_CONFIG_DIR, "configuration-qemu-snp.toml")
        elif "qemu-tdx" in sc2_runtime:
            src_conf_path = join(KATA_CONFIG_DIR, "configuration-qemu-tdx.toml")
        dst_conf_path = join(KATA_CONFIG_DIR, f"configuration-{sc2_runtime}.toml")
        run(f"sudo cp {src_conf_path} {dst_conf_path}", shell=True, check=True)

        # Patch config file to enable VM cache
        # FIXME: we need to update the default_memory to be able to run the
        # Knative chaining test. This will change when memory hot-plugging
        # is supported
        # FIXME 2: we need to set the default max vcpus, as the kata-runtime,
        # and containerd-shim seem to give it different default values. Not
        # an issue as hot-plugging vCPUs is not supported so we can never
        # exceed the default (1).
        updated_toml_str = """
        [factory]
        vm_cache_number = {vm_cache_number}

        [hypervisor.qemu]
        hot_plug_vfio = "root-port"
        pcie_root_port = 2
        default_memory = 6144
        default_maxvcpus = 1
        """.format(
            vm_cache_number=VM_CACHE_SIZE
        )
        update_toml(dst_conf_path, updated_toml_str)

        # Update containerd to point the SC2 runtime to the right config
        updated_toml_str = """
        [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.kata-{runtime_name}.options]
        ConfigPath = "{conf_path}"
        """.format(
            runtime_name=sc2_runtime, conf_path=dst_conf_path
        )
        update_toml(CONTAINERD_CONFIG_FILE, updated_toml_str)

    # Install runttime class on kubernetes
    if debug:
        print("Installing SC2 runtime class...")
    for sc2_runtime in SC2_RUNTIMES:
        sc2_runtime_file = join(CONF_FILES_DIR, f"{sc2_runtime}_runtimeclass.yaml")
        run_kubectl_command(f"create -f {sc2_runtime_file}", capture_output=not debug)
    expected_runtime_classes = [
        "kata",
        "kata-clh",
        "kata-qemu",
        "kata-qemu-coco-dev",
        "kata-qemu-sev",
        "kata-qemu-snp",
        "kata-qemu-snp-sc2",
        "kata-qemu-tdx",
        "kata-qemu-tdx-sc2",
    ]
    run_class_cmd = "get runtimeclass -o jsonpath='{.items..handler}'"
    runtime_classes = run_kubectl_command(run_class_cmd, capture_output=True).split(" ")
    while len(expected_runtime_classes) != len(runtime_classes):
        if debug:
            print(
                "Not all expected runtime classes are registered ({} != {})".format(
                    len(expected_runtime_classes), len(runtime_classes)
                )
            )

        sleep(5)
        runtime_classes = run_kubectl_command(run_class_cmd, capture_output=True).split(
            " "
        )

    # Replace the agent in the initrd
    if debug:
        print("Replacing kata agent...")
    replace_kata_agent(
        dst_initrd_path=join(
            KATA_IMG_DIR, "kata-containers-initrd-confidential-sc2.img"
        ),
        debug=False,
        sc2=True,
    )

    # Replace the kata shim
    if debug:
        print("Replacing kata shim...")
    replace_kata_shim(
        dst_shim_binary=join(KATA_ROOT, "bin", "containerd-shim-kata-sc2-v2"),
        sc2=True,
    )


@task(default=True)
def deploy(ctx, debug=False, clean=False):
    """
    Deploy an SC2-enabled bare-metal Kubernetes cluster
    """
    # Fail-fast if deployment exists
    if exists(SC2_DEPLOYMENT_FILE):
        print(f"ERROR: SC2 already deployed (file {SC2_DEPLOYMENT_FILE} exists)")
        print("ERROR: only remove deployment file if you know what you are doing!")
        raise RuntimeError("SC2 already deployed!")

    if clean:
        # Remove all directories that we populate and modify
        for nuked_dir in [
            COCO_ROOT,
            CONTAINERD_CONFIG_ROOT,
            HOST_CERT_DIR,
            KATA_ROOT,
            SC2_CONFIG_DIR,
        ]:
            if debug:
                print(f"WARNING: nuking {nuked_dir}")
            run(f"sudo rm -rf {nuked_dir}", shell=True, check=True)

        # Purge VM cache for a very-clean start
        vm_cache_dir = join(PROJ_ROOT, "vm-cache")
        result = run(
            "sudo target/release/vm-cache prune",
            cwd=vm_cache_dir,
            shell=True,
            capture_output=True,
        )
        assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
        if debug:
            print(result.stdout.decode("utf-8").strip())

        # Purge containerd for a very-clean start
        purge_containerd_dir = join(PROJ_ROOT, "tools", "purge-containerd")
        result = run(
            "cargo build --release && sudo target/release/purge-containerd",
            cwd=purge_containerd_dir,
            shell=True,
            capture_output=True,
        )
        assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
        if debug:
            print(result.stdout.decode("utf-8").strip())

    # Create SC2 config dir
    if not exists(SC2_CONFIG_DIR):
        makedirs(SC2_CONFIG_DIR)

    # Disable swap
    run("sudo swapoff -a", shell=True, check=True)

    # Build and install containerd
    containerd_install(debug=debug, clean=clean)

    # Install k8s tooling (including k9s)
    k8s_tooling_install(debug=debug, clean=clean)
    k9s_install(debug=debug)

    # Create a single-node k8s cluster
    k8s_create(debug=debug)

    # Install the CoCo operator as well as the CC-runtimes
    operator_install(debug=debug)
    operator_install_cc_runtime(debug=debug)

    # Install the nydus-snapshotter (must happen after we install CoCo)
    nydus_snapshotter_install(debug=debug, clean=clean)

    # Install the nydusify tool
    nydus_install()

    # Start a local docker registry (must happen before knative installation,
    # as we rely on it to host our sidecar image)
    start_local_registry(debug=debug, clean=clean)

    # Install Knative
    knative_install(debug=debug)

    # Apply general patches to the Kata Agent (and initrd), making sure we
    # have the latest patched version
    print_dotted_line(f"Pulling latest Kata image (v{KATA_VERSION})")
    result = run(f"docker pull {KATA_IMAGE_TAG}", shell=True, capture_output=True)
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
    if debug:
        print(result.stdout.decode("utf-8").strip())
    replace_kata_agent(
        dst_initrd_path=join(
            KATA_IMG_DIR, "kata-containers-initrd-confidential-sc2-baseline.img"
        ),
        debug=debug,
        sc2=False,
    )
    print("Success!")

    # Install sc2 runtime with patches
    print_dotted_line(f"Installing SC2 (v{COCO_VERSION})")
    install_sc2_runtime(debug=debug)
    print("Success!")

    # Build and install the guest VM kernel (must be after installing SC2, so
    # that we can patch all config files)
    print_dotted_line(f"Build and install guest VM kernel (v{GUEST_KERNEL_VERSION})")
    build_guest_kernel()
    print("Success!")

    # Once we are done with installing components, restart containerd
    restart_containerd(debug=debug)

    # Start the VM cache at the end so that we can pick up the latest config
    # changes
    print_dotted_line("Starting cVM cache...")
    start_vm_cache(debug=debug)
    print("Success!")

    # Push demo apps to local registry for easy testing
    push_demo_apps_to_local_registry(debug=debug)

    # Finally, create a deployment file (right now, it is empty)
    result = run(f"touch {SC2_DEPLOYMENT_FILE}", shell=True, capture_output=True)
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
    if debug:
        print(result.stdout.decode("utf-8").strip())


@task
def destroy(ctx, debug=False):
    """
    Destroy an SC2 cluster
    """
    # Stop VM cache server (must happen before k8s_destroy to make sure all
    # our config files are there)
    vm_cache_dir = join(PROJ_ROOT, "vm-cache")
    result = run(
        "sudo target/release/vm-cache stop",
        cwd=vm_cache_dir,
        shell=True,
        capture_output=True,
    )
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
    if debug:
        print(result.stdout.decode("utf-8").strip())

    # Stop docker registry (must happen before k8s_destroy, as we need to
    # delete secrets from the cluster)
    stop_local_registry(debug=debug)

    # Destroy k8s cluster
    k8s_destroy(debug=debug)

    # Remove deployment file
    result = run(f"rm -f {SC2_DEPLOYMENT_FILE}", shell=True, capture_output=True)
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
    if debug:
        print(result.stdout.decode("utf-8").strip())


@task
def set_log_level(ctx, log_level):
    """
    Set log level for all SC2 containers: containerd, kata, and nydus-snapshotter
    """
    allowed_log_levels = ["info", "debug"]
    if log_level not in allowed_log_levels:
        print(
            "Unsupported log level '{}'. Must be one in: {}".format(
                log_level, allowed_log_levels
            )
        )
        return

    containerd_set_log_level(log_level)
    kata_set_log_level(log_level)
    nydus_snapshotter_set_log_level(log_level)
