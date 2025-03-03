#!/usr/bin/env bats

load utils/env.sh

setup_file() {
    load utils/helpers.sh

    set_snapshotter_mode "host-share"
}

# Make sure we purge before each test so that we have a cold start
setup() {
    load utils/helpers.sh

    ${INV} nydus-snapshotter.purge
}

teardown() {
    load utils/helpers.sh

    common_teardown
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
