#!/usr/bin/env bats

setup_file() {
    load utils/env.sh
    load utils/helpers.sh

    set_snapshotter_mode "host-share"
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

TEST_NAME="Test knative hello world"
snapshotter="host-share"

# ------------------------------------------------------------------------------
# Nydus Snapshotter in Host Share mode
#
# Using the snapshotter in host-share mode is only supported for SC2 runtimes,
# as we have only implemented the patches in our forked branches.
# ------------------------------------------------------------------------------

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[3]} snapshotter=${snapshotter}" {
    [[ "$SC2_TEE" == "tdx" ]] && skip "#142"
    run_python_hello_world "${SC2_RUNTIME_CLASSES[3]}"
}

