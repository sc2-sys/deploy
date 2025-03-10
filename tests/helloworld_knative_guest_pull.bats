#!/usr/bin/env bats

load utils/env.sh

setup_file() {
    load utils/helpers.sh

    set_snapshotter_mode "guest-pull"
}

setup() {
    load utils/helpers.sh
}

teardown() {
    load utils/helpers.sh

    common_teardown
}

TEST_NAME="Test knative hello world"
snapshotter="guest-pull"

# ------------------------------------------------------------------------------
# Nydus Snapshotter in Guest Pull mode
# ------------------------------------------------------------------------------

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[0]} snapshotter=${snapshotter}" {
    timeout "${SC2_TEST_TIMEOUT}" bash -c '
        source ./tests/utils/helpers.sh
        run_knative_hello_world "${SC2_RUNTIME_CLASSES[0]}"
    '

    cleanup_knative_hello_world
}

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[1]} snapshotter=${snapshotter}" {
    timeout "${SC2_TEST_TIMEOUT}" bash -c '
        source ./tests/utils/helpers.sh
        run_knative_hello_world "${SC2_RUNTIME_CLASSES[1]}"
    '

    cleanup_knative_hello_world
}

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[2]} snapshotter=${snapshotter}" {
    timeout "${SC2_TEST_TIMEOUT}" bash -c '
        source ./tests/utils/helpers.sh
        run_knative_hello_world "${SC2_RUNTIME_CLASSES[2]}"
    '

    cleanup_knative_hello_world
}

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[3]} snapshotter=${snapshotter}" {
    timeout "${SC2_TEST_TIMEOUT}" bash -c '
        source ./tests/utils/helpers.sh
        run_knative_hello_world "${SC2_RUNTIME_CLASSES[3]}"
    '

    cleanup_knative_hello_world
}
