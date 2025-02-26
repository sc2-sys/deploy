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
    ${KUBECTL} delete namespace ${SC2_DEMO_NAMESPACE} --ignore-not-found

    # Cautionary inter-test sleep
    sleep ${INTERTEST_SLEEP_SECS}
}

TEST_NAME="Test python hello world"
snapshotter="guest-pull"

# ------------------------------------------------------------------------------
# Nydus Snapshotter in Guest Pull mode
# ------------------------------------------------------------------------------

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[0]} snapshotter=${snapshotter}" {
    run_python_hello_world "${SC2_RUNTIME_CLASSES[0]}"
}

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[1]} snapshotter=${snapshotter}" {
    run_python_hello_world "${SC2_RUNTIME_CLASSES[1]}"
}

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[2]} snapshotter=${snapshotter}" {
    run_python_hello_world "${SC2_RUNTIME_CLASSES[2]}"
}

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[3]} snapshotter=${snapshotter}" {
    run_python_hello_world "${SC2_RUNTIME_CLASSES[3]}"
}
