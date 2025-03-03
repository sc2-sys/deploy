#!/usr/bin/env bats

load utils/env.sh

setup_file() {
    load utils/helpers.sh

    set_snapshotter_mode "guest-pull"
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

snapshotter="guest-pull"

# ------------------------------------------------------------------------------
# Python cold starts
# ------------------------------------------------------------------------------

@test "Test python cold starts: runtime=${SC2_RUNTIME_CLASSES[0]} snapshotter=${snapshotter}" {
    timeout "${SC2_TEST_TIMEOUT}" bash -c '
        source ./tests/utils/helpers.sh
        run_python_hello_world "${SC2_RUNTIME_CLASSES[0]}"
    '

    cleanup_python_hello_world
}

@test "Test python cold starts: runtime=${SC2_RUNTIME_CLASSES[1]} snapshotter=${snapshotter}" {
    timeout "${SC2_TEST_TIMEOUT}" bash -c '
        source ./tests/utils/helpers.sh
        run_python_hello_world "${SC2_RUNTIME_CLASSES[1]}"
    '

    cleanup_python_hello_world
}

@test "Test python cold starts: runtime=${SC2_RUNTIME_CLASSES[2]} snapshotter=${snapshotter}" {
    timeout "${SC2_TEST_TIMEOUT}" bash -c '
        source ./tests/utils/helpers.sh
        run_python_hello_world "${SC2_RUNTIME_CLASSES[2]}"
    '

    cleanup_python_hello_world
}

@test "Test python cold starts: runtime=${SC2_RUNTIME_CLASSES[3]} snapshotter=${snapshotter}" {
    timeout "${SC2_TEST_TIMEOUT}" bash -c '
        source ./tests/utils/helpers.sh
        run_python_hello_world "${SC2_RUNTIME_CLASSES[3]}"
    '

    cleanup_python_hello_world
}

# ------------------------------------------------------------------------------
# Knative cold starts
# ------------------------------------------------------------------------------

@test "Test knative cold starts: runtime=${SC2_RUNTIME_CLASSES[0]} snapshotter=${snapshotter}" {
    timeout "${SC2_TEST_TIMEOUT}" bash -c '
        source ./tests/utils/helpers.sh
        run_knative_hello_world "${SC2_RUNTIME_CLASSES[0]}"
    '

    cleanup_knative_hello_world
}

@test "Test knative cold starts: runtime=${SC2_RUNTIME_CLASSES[1]} snapshotter=${snapshotter}" {
    timeout "${SC2_TEST_TIMEOUT}" bash -c '
        source ./tests/utils/helpers.sh
        run_knative_hello_world "${SC2_RUNTIME_CLASSES[1]}"
    '

    cleanup_knative_hello_world
}

@test "Test knative cold starts: runtime=${SC2_RUNTIME_CLASSES[2]} snapshotter=${snapshotter}" {
    timeout "${SC2_TEST_TIMEOUT}" bash -c '
        source ./tests/utils/helpers.sh
        run_knative_hello_world "${SC2_RUNTIME_CLASSES[2]}"
    '

    cleanup_knative_hello_world
}

@test "Test knative cold starts: runtime=${SC2_RUNTIME_CLASSES[3]} snapshotter=${snapshotter}" {
    timeout "${SC2_TEST_TIMEOUT}" bash -c '
        source ./tests/utils/helpers.sh
        run_knative_hello_world "${SC2_RUNTIME_CLASSES[3]}"
    '

    cleanup_knative_hello_world
}
