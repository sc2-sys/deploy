#!/usr/bin/env bats

# Define an array of test values
VALUES=("one" "two" "three")

setup() {
    if [ -n "$SC2_TEE" ]; then
        if [ "$SC2_TEE" == "snp" ]; then
            SC2_RUNTIME_CLASSES=("qemu" "qemu-coco-dev" "qemu-snp" "qemu-snp-sc2")
        elif [ "$SC2_TEE" == "tdx" ]; then
            SC2_RUNTIME_CLASSES=("qemu" "qemu-coco-dev" "qemu-tdx" "qemu-tdx-sc2")
        else
            echo "ERROR: SC2_TEE env. var must be one in: 'snp', 'tdx'"
            exit 1
        fi
    else
        echo "ERROR: SC2_TEE env. var must be set"
        exit 1
    fi

  # Set the TEST_VALUE based on the array and current test number
  export SC2_RUNTIME_CLASS="${SC2_RUNTIME_CLASSES[$((bats_test_number - 1))]}"
}

# TODO: cold/warm starts and guest-pull host-share
@test "Check python hello world" {
    # TODO: move a lot to helper functions
    echo "Running test for $SC2_RUNTIME_CLASS"
    envsubst < ./demo-apps/helloworld-py/deployment.yaml | ./bin/kubectl apply -f -

    export POD_LABEL="apps.sc2.io/name=helloworld-py"
    # Wait for pod to be ready
    until [ "$(./bin/kubectl get pods -l ${POD_LABEL} -o 'jsonpath={..status.conditions[?(@.type=="Ready")].status}')" = "True" ]; do echo "Waiting for pod to be ready..."; sleep 2; done
    sleep 1

    # Get the pod's IP
    service_ip=$(./bin/kubectl get services -o jsonpath='{.items[?(@.metadata.name=="coco-helloworld-py-node-port")].spec.clusterIP}')
    [ "$(curl --retry 3 -X GET ${service_ip}:8080)" = "Hello World!" ]

    envsubst < ./demo-apps/helloworld-py/deployment.yaml | ./bin/kubectl delete -f -

    # Wait for pod to be deleted
    ./bin/kubectl wait --for=delete -l ${POD_LABEL} pod --timeout=30s
    # Extra cautionary sleep
    sleep 5
    echo "Test for ${runtime_class} (${flavour}) successful!"
}
