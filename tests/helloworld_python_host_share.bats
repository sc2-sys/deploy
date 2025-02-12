#!/usr/bin/env bats

source ./tests/utils/env.sh
source ./tests/utils/helpers.sh

setup_file() {
    set_snapshotter_mode "host-share"
}

teardown() {
    # Cautionary inter-test sleep
    sleep 5
}

TEST_NAME="Test python hello world"
snapshotter="host-share"

# ------------------------------------------------------------------------------
# Nydus Snapshotter in Host Share mode
#
# Using the snapshotter in host-share mode is only supported for SC2 runtimes,
# as we have only implemented the patches in our forked branches.
# ------------------------------------------------------------------------------

@test "${TEST_NAME}: runtime=${SC2_RUNTIME_CLASSES[3]} snapshotter=${snapshotter}" {
    [[ "$SC2_TEE" == "tdx" ]] && skip "Host-share not supported for TDX (#142)"
    run_python_hello_world "${SC2_RUNTIME_CLASSES[3]}"
}

