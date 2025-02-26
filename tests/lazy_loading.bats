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

snapshotter="guest-pull"

@test "Test python lazy loading: runtime=${SC2_RUNTIME_CLASSES[3]} snapshotter=${snapshotter}" {
    run_python_lazy_loading "${SC2_RUNTIME_CLASSES[3]}"
}

@test "Test knative lazy loading: runtime=${SC2_RUNTIME_CLASSES[3]} snapshotter=${snapshotter}" {
    run_knative_lazy_loading "${SC2_RUNTIME_CLASSES[3]}"
}
