from invoke import Collection

from . import apps
from . import coco
from . import containerd
from . import cosign
from . import format_code
from . import k8s
from . import k9s
from . import kata
from . import kbs
from . import knative
from . import kubeadm
from . import operator
from . import sev

ns = Collection(
    apps,
    coco,
    containerd,
    cosign,
    format_code,
    k8s,
    k9s,
    kata,
    kbs,
    knative,
    kubeadm,
    operator,
    sev,
)
