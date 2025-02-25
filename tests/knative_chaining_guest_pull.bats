#!/usr/bin/env bats

setup_file() {
    load utils/env.sh
    load utils/helpers.sh

    set_snapshotter_mode "guest-pull"
}

setup() {
    load utils/env.sh
    load utils/helpers.sh
}

teardown() {
    # Cautionary inter-test sleep
    sleep ${INTERTEST_SLEEP_SECS}
}

TEST_NAME="Test knative chaining"
snapshotter="guest-pull"

# ------------------------------------------------------------------------------
# Nydus Snapshotter in Guest Pull mode
# ------------------------------------------------------------------------------

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[0]} snapshotter=${snapshotter}" {
    enable_kata_annotation "default_memory" "${SC2_RUNTIME_CLASSES[0]}"

    run_knative_chaining "${SC2_RUNTIME_CLASSES[0]}"
}

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[1]} snapshotter=${snapshotter}" {
    enable_kata_annotation "default_memory" "${SC2_RUNTIME_CLASSES[1]}"

    run_knative_chaining "${SC2_RUNTIME_CLASSES[1]}"
}

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[2]} snapshotter=${snapshotter}" {
    enable_kata_annotation "default_memory" "${SC2_RUNTIME_CLASSES[2]}"

    run_knative_chaining "${SC2_RUNTIME_CLASSES[2]}"
}

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[3]} snapshotter=${snapshotter}" {
    enable_kata_annotation "default_memory" "${SC2_RUNTIME_CLASSES[3]}"
    restart_vm_cache

    run_knative_chaining "${SC2_RUNTIME_CLASSES[3]}"
}
