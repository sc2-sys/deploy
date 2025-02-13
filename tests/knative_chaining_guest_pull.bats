#!/usr/bin/env bats

source ./tests/utils/env.sh
source ./tests/utils/helpers.sh

setup_file() {
    set_snapshotter_mode "guest-pull"

    # The chaining tests need more memory and we set it using the
    # default_memory annotation
    enable_kata_annotation "default_memory"
    restart_vm_cache

    # May have to fetch content here
    k8s_content_fetch ${PAUSE_IMAGE}
    k8s_content_fetch ${SIDECAR_IMAGE}
}

teardown() {
    # Cautionary inter-test sleep
    sleep 5
}

TEST_NAME="Test knative chaining"
snapshotter="guest-pull"

# ------------------------------------------------------------------------------
# Nydus Snapshotter in Guest Pull mode
# ------------------------------------------------------------------------------

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[0]} snapshotter=${snapshotter}" {
    run_knative_chaining "${SC2_RUNTIME_CLASSES[0]}"
}

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[1]} snapshotter=${snapshotter}" {
    run_knative_chaining "${SC2_RUNTIME_CLASSES[1]}"
}

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[2]} snapshotter=${snapshotter}" {
    run_knative_chaining "${SC2_RUNTIME_CLASSES[2]}"
}

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[3]} snapshotter=${snapshotter}" {
    run_knative_chaining "${SC2_RUNTIME_CLASSES[3]}"
}
