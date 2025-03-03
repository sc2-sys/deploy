#!/usr/bin/env bats

load utils/env.sh

setup_file() {
    load utils/helpers.sh

    set_snapshotter_mode "guest-pull"
}

setup() {
    load utils/helpers.sh

    # Longer timeout for chaining tests
    export SC2_TEST_TIMEOUT=180
}

teardown() {
    load utils/helpers.sh

    common_teardown
}

TEST_NAME="Test knative chaining"
snapshotter="guest-pull"

# ------------------------------------------------------------------------------
# Nydus Snapshotter in Guest Pull mode
# ------------------------------------------------------------------------------

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[0]} snapshotter=${snapshotter}" {
    enable_kata_annotation "default_memory" "${SC2_RUNTIME_CLASSES[0]}"

    timeout "${SC2_TEST_TIMEOUT}" bash -c '
        source ./tests/utils/helpers.sh
        run_knative_chaining "${SC2_RUNTIME_CLASSES[0]}"
    '

    cleanup_knative_chaining
}

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[1]} snapshotter=${snapshotter}" {
    enable_kata_annotation "default_memory" "${SC2_RUNTIME_CLASSES[1]}"

    timeout "${SC2_TEST_TIMEOUT}" bash -c '
        source ./tests/utils/helpers.sh
        run_knative_chaining "${SC2_RUNTIME_CLASSES[1]}"
    '

    cleanup_knative_chaining
}

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[2]} snapshotter=${snapshotter}" {
    enable_kata_annotation "default_memory" "${SC2_RUNTIME_CLASSES[2]}"

    timeout "${SC2_TEST_TIMEOUT}" bash -c '
        source ./tests/utils/helpers.sh
        run_knative_chaining "${SC2_RUNTIME_CLASSES[2]}"
    '

    cleanup_knative_chaining
}

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[3]} snapshotter=${snapshotter}" {
    enable_kata_annotation "default_memory" "${SC2_RUNTIME_CLASSES[3]}"
    restart_vm_cache

    timeout "${SC2_TEST_TIMEOUT}" bash -c '
        source ./tests/utils/helpers.sh
        run_knative_chaining "${SC2_RUNTIME_CLASSES[3]}"
    '

    cleanup_knative_chaining
}
