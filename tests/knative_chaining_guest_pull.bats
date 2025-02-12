#!/usr/bin/env bats

source ./tests/utils/env.sh
source ./tests/utils/helpers.sh

setup_file() {
    set_snapshotter_mode "guest-pull"
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
