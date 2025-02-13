#!/usr/bin/env bats

source ./tests/utils/env.sh
source ./tests/utils/helpers.sh

setup_file() {
    set_snapshotter_mode "host-share"
}

# Make sure we purge before each test so that we have a cold start
setup() {
    ${INV} nydus-snapshotter.purge
}

teardown() {
    # Cautionary inter-test sleep
    sleep 5
}

snapshotter="host-share"

# ------------------------------------------------------------------------------
# Python cold starts
# ------------------------------------------------------------------------------

@test "Test python cold starts: runtime=${SC2_RUNTIME_CLASSES[3]} snapshotter=${snapshotter}" {
    run_python_hello_world "${SC2_RUNTIME_CLASSES[3]}"
}

# ------------------------------------------------------------------------------
# Knative cold starts
# ------------------------------------------------------------------------------

@test "Test knative cold starts: runtime=${SC2_RUNTIME_CLASSES[3]} snapshotter=${snapshotter}" {
    run_knative_hello_world "${SC2_RUNTIME_CLASSES[3]}"
}
