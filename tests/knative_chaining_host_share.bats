#!/usr/bin/env bats

load utils/env.sh

setup_file() {
    load utils/helpers.sh

    set_snapshotter_mode "host-share"
}

setup() {
    load utils/helpers.sh

    # Longer timeout for chaining tests
    export SC2_TEST_TIMEOUT=120
}

teardown() {
    load utils/helpers.sh

    common_teardown
}

TEST_NAME="Test knative chaining"
snapshotter="host-share"

# ------------------------------------------------------------------------------
# Nydus Snapshotter in Host Share mode
#
# Using the snapshotter in host-share mode is only supported for SC2 runtimes,
# as we have only implemented the patches in our forked branches.
# ------------------------------------------------------------------------------

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[3]} snapshotter=${snapshotter}" {
    [[ "$SC2_TEE" == "tdx" ]] && skip "#142"

    enable_kata_annotation "default_memory" "${SC2_RUNTIME_CLASSES[3]}"
    restart_vm_cache

    timeout "${SC2_TEST_TIMEOUT}" bash -c '
        source ./tests/utils/helpers.sh
        run_knative_chaining "${SC2_RUNTIME_CLASSES[3]}"
    '

    cleanup_knative_chaining
}

