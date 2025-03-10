from os.path import dirname, expanduser, realpath, join
from subprocess import run
from tasks.util.versions import PAUSE_IMAGE_VERSION

PROJ_ROOT = dirname(dirname(dirname(realpath(__file__))))

BIN_DIR = join(PROJ_ROOT, "bin")
GLOBAL_BIN_DIR = "/usr/local/bin"
GLOBAL_INSTALL_DIR = "/opt"
COMPONENTS_DIR = join(PROJ_ROOT, "components")
CONF_FILES_DIR = join(PROJ_ROOT, "conf-files")
TEMPLATED_FILES_DIR = join(PROJ_ROOT, "templated")

# K8s Config

K8S_CONFIG_DIR = join(PROJ_ROOT, ".config")
K8S_ADMIN_FILE = join(CONF_FILES_DIR, "kubeadm.conf")
K8S_CONFIG_FILE = "/etc/kubernetes/admin.conf"
# This value is hardcoded in ./.config/kubeadm.conf
CRI_RUNTIME_SOCKET = "unix:///run/containerd/containerd.sock"
PAUSE_IMAGE_REPO = "docker://registry.k8s.io/pause"
PAUSE_IMAGE = f"{PAUSE_IMAGE_REPO}:{PAUSE_IMAGE_VERSION}"

# Containerd

CONTAINERD_CONFIG_ROOT = "/etc/containerd"
CONTAINERD_CONFIG_FILE = join(CONTAINERD_CONFIG_ROOT, "config.toml")

# Image Registry config

LOCAL_REGISTRY_URL = "sc2cr.io"
GHCR_URL = "ghcr.io"
GITHUB_ORG = "sc2-sys"

# Kubeadm config

KUBEADM_KUBECONFIG_FILE = join(K8S_CONFIG_DIR, "kubeadm_kubeconfig")

# CoCo config
COCO_ROOT = join("/opt", "confidential-containers")
KATA_ROOT = join("/opt", "kata")

# ---------- Kata config ----------

KATA_CONFIG_DIR = join(KATA_ROOT, "share", "defaults", "kata-containers")
KATA_IMG_DIR = join(KATA_ROOT, "share", "kata-containers")
KATA_WORKON_CTR_NAME = "kata-workon"
KATA_RUNTIMES = ["qemu-coco-dev", "qemu-snp", "qemu-tdx"]

# ---------- SC2 config ----------

SC2_ROOT = "/opt/sc2"
SC2_CONFIG_DIR = join(expanduser("~"), ".config", "sc2")
SC2_DEPLOYMENT_FILE = join(SC2_CONFIG_DIR, "DEPLOYED")
SC2_RUNTIMES = ["qemu-snp-sc2", "qemu-tdx-sc2"]

# ---------- Apps config ----------

APPS_SOURCE_DIR = join(PROJ_ROOT, "demo-apps")

# KBS Config

KBS_PORT = 44444

# VM Cache config

VM_CACHE_SIZE = 10


def print_dotted_line(message, dot_length=90):
    dots = "." * (dot_length - len(message))
    print(f"{message}{dots}", end="", flush=True)


def get_node_url():
    """
    Get the external node IP that can be reached from both host and guest

    This IP is both used for the KBS, and for deploying a local docker registry.

    If the KBS is deployed using docker compose with host networking and the
    port is forwarded to the host (i.e. KBS is bound to :${KBS_PORT}, then
    we can use this method to figure out the "public-facing" IP that can be
    reached both from the host and the guest
    """
    ip_cmd = "ip -o route get to 8.8.8.8"
    ip_cmd_out = (
        run(ip_cmd, shell=True, capture_output=True)
        .stdout.decode("utf-8")
        .strip()
        .split(" ")
    )
    idx = ip_cmd_out.index("src") + 1
    kbs_url = ip_cmd_out[idx]
    return kbs_url
