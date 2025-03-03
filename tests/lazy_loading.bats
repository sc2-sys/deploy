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

snapshotter="guest-pull"

@test "Test python lazy loading: runtime=${SC2_RUNTIME_CLASSES[3]} snapshotter=${snapshotter}" {
    timeout "${SC2_TEST_TIMEOUT}" bash -c '
        source ./tests/utils/helpers.sh
        run_python_lazy_loading "${SC2_RUNTIME_CLASSES[3]}"
    '

    cleanup_python_hello_world
}

@test "Test knative lazy loading: runtime=${SC2_RUNTIME_CLASSES[3]} snapshotter=${snapshotter}" {
    timeout "${SC2_TEST_TIMEOUT}" bash -c '
        source ./tests/utils/helpers.sh
        run_knative_lazy_loading "${SC2_RUNTIME_CLASSES[3]}"
    '

    cleanup_knative_hello_world
}
