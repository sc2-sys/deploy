#!/bin/bash

THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

export PROJ_ROOT=${THIS_DIR}/../..
export KUBECTL=${PROJ_ROOT}/bin/kubectl
export INV=${PROJ_ROOT}/bin/inv_wrapper.sh

# Work out the runtime classes from the env. var
if [ -n "$SC2_TEE" ]; then
    if [ "$SC2_TEE" == "snp" ]; then
        export SC2_RUNTIME_CLASSES=("qemu" "qemu-coco-dev" "qemu-snp" "qemu-snp-sc2")
    elif [ "$SC2_TEE" == "tdx" ]; then
        export SC2_RUNTIME_CLASSES=("qemu" "qemu-coco-dev" "qemu-tdx" "qemu-tdx-sc2")
    else
        echo "ERROR: SC2_TEE env. var must be one in: 'snp', 'tdx'"
        exit 1
    fi
else
    echo "ERROR: SC2_TEE env. var must be set"
    exit 1
fi

# Useful constants
INTERTEST_SLEEP_SECS=5

# Images
PAUSE_IMAGE="registry.k8s.io/pause:3.8"
SIDECAR_IMAGE="sc2cr.io/system/knative-sidecar@sha256:79d5f6031f308cee209c4c32eeab9113b29a1ed4096c5d657504096734ca3b1d"
