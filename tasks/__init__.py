from invoke import Collection

from . import coco
from . import containerd
from . import cosign
from . import demo_apps
from . import docker
from . import format_code
from . import gc
from . import kernel
from . import k8s
from . import k9s
from . import kata
from . import knative
from . import kubeadm
from . import nydus
from . import nydus_snapshotter
from . import operator
from . import ovmf
from . import qemu
from . import registry
from . import sc2
from . import sev
from . import skopeo
from . import svsm
from . import trustee

ns = Collection(
    coco,
    containerd,
    cosign,
    demo_apps,
    docker,
    format_code,
    gc,
    k8s,
    k9s,
    kata,
    kernel,
    knative,
    kubeadm,
    nydus,
    nydus_snapshotter,
    operator,
    ovmf,
    qemu,
    registry,
    sc2,
    sev,
    skopeo,
    svsm,
    trustee,
)
