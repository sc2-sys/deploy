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

snapshotter="guest-pull"

@test "Test python lazy loading: runtime=${SC2_RUNTIME_CLASSES[3]} snapshotter=${snapshotter}" {
    run_python_lazy_loading "${SC2_RUNTIME_CLASSES[3]}"
}

@test "Test knative lazy loading: runtime=${SC2_RUNTIME_CLASSES[3]} snapshotter=${snapshotter}" {
    run_knative_lazy_loading "${SC2_RUNTIME_CLASSES[3]}"
}
