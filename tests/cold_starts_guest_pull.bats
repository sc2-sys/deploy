#!/usr/bin/env bats

load utils/env.sh

setup_file() {
    load utils/env.sh
    load utils/helpers.sh

    set_snapshotter_mode "guest-pull"
}

# Make sure we purge before each test so that we have a cold start
setup() {
    load utils/env.sh
    load utils/helpers.sh

    ${INV} nydus-snapshotter.purge
}

teardown() {
    # Cautionary inter-test sleep
    sleep ${INTERTEST_SLEEP_SECS}
}

snapshotter="guest-pull"

# ------------------------------------------------------------------------------
# Python cold starts
# ------------------------------------------------------------------------------

@test "Test python cold starts: runtime=${SC2_RUNTIME_CLASSES[0]} snapshotter=${snapshotter}" {
    run_python_hello_world "${SC2_RUNTIME_CLASSES[0]}"
}

@test "Test python cold starts: runtime=${SC2_RUNTIME_CLASSES[1]} snapshotter=${snapshotter}" {
    run_python_hello_world "${SC2_RUNTIME_CLASSES[1]}"
}

@test "Test python cold starts: runtime=${SC2_RUNTIME_CLASSES[2]} snapshotter=${snapshotter}" {
    run_python_hello_world "${SC2_RUNTIME_CLASSES[2]}"
}

@test "Test python cold starts: runtime=${SC2_RUNTIME_CLASSES[3]} snapshotter=${snapshotter}" {
    run_python_hello_world "${SC2_RUNTIME_CLASSES[3]}"
}

# ------------------------------------------------------------------------------
# Knative cold starts
# ------------------------------------------------------------------------------

@test "Test knative cold starts: runtime=${SC2_RUNTIME_CLASSES[0]} snapshotter=${snapshotter}" {
    run_knative_hello_world "${SC2_RUNTIME_CLASSES[0]}"
}

@test "Test knative cold starts: runtime=${SC2_RUNTIME_CLASSES[1]} snapshotter=${snapshotter}" {
    run_knative_hello_world "${SC2_RUNTIME_CLASSES[1]}"
}

@test "Test knative cold starts: runtime=${SC2_RUNTIME_CLASSES[2]} snapshotter=${snapshotter}" {
    run_knative_hello_world "${SC2_RUNTIME_CLASSES[2]}"
}

@test "Test knative cold starts: runtime=${SC2_RUNTIME_CLASSES[3]} snapshotter=${snapshotter}" {
    run_knative_hello_world "${SC2_RUNTIME_CLASSES[3]}"
}
