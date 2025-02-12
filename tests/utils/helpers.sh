#!/bin/bash

source ./tests/utils/env.sh

# ------------------------------------------------------------------------------
# Helper functions to set-up the environment
# ------------------------------------------------------------------------------

set_snapshotter_mode() {
    local snapshotter_mode="$1"
    ${INV} nydus-snapshotter.set-mode ${snapshotter_mode}
    ${INV} nydus-snapshotter.purge

    export SC2_SNAPSHOTTER=${snapshotter_mode}

    sleep 1
}

# ------------------------------------------------------------------------------
# Helper functions to run specific workloads
# ------------------------------------------------------------------------------

run_python_hello_world() {
    local runtime_class="$1"
    export SC2_RUNTIME_CLASS="$runtime_class"

    envsubst < ./demo-apps/helloworld-py/deployment.yaml | ${KUBECTL} apply -f -

    export POD_LABEL="apps.sc2.io/name=helloworld-py"

    # Wait for pod to be ready
    until [ "$(${KUBECTL} get pods -l ${POD_LABEL} -o 'jsonpath={..status.conditions[?(@.type=="Ready")].status}')" = "True" ]; do echo "Waiting for pod to be ready..."; sleep 2; done
    sleep 1

    # Get the pod's IP
    service_ip=$(${KUBECTL} get services -o jsonpath='{.items[?(@.metadata.name=="coco-helloworld-py-node-port")].spec.clusterIP}')
    [ "$(curl --retry 3 -X GET ${service_ip}:8080)" = "Hello World!" ]

    envsubst < ./demo-apps/helloworld-py/deployment.yaml | ${KUBECTL} delete -f -

    # Wait for pod to be deleted
    ${KUBECTL} wait --for=delete -l ${POD_LABEL} pod --timeout=30s
}

run_knative_hello_world() {
    local runtime_class="$1"
    export SC2_RUNTIME_CLASS="$runtime_class"

    envsubst < ./demo-apps/helloworld-knative/service.yaml | ${KUBECTL} apply -f -
    sleep 1

    # Get the service URL
    service_url=$(${KUBECTL} get ksvc helloworld-knative  --output=custom-columns=URL:.status.url --no-headers)
    [ "$(curl --retry 3 ${service_url})" = "Hello World!" ]

    # Wait for pod to be deleted
    POD_LABEL="apps.sc2.io/name=helloworld-py"
    envsubst < ./demo-apps/helloworld-knative/service.yaml | ${KUBECTL} delete -f -
    ${KUBECTL} wait --for=delete -l ${POD_LABEL} pod --timeout=60s
}

run_knative_chaining() {
    local runtime_class="$1"
    export SC2_RUNTIME_CLASS="$runtime_class"

    envsubst < ./demo-apps/knative-chaining/chaining.yaml | ${KUBECTL} apply -f -
    sleep 1

    # Curl the channel URL
    ./demo-apps/knative-chaining/curl_cmd.sh

    NAMESPACE="chaining-test"
    POD_LABEL="apps.sc2.io/name=knative-chaining-three"

    # Wait for pod 3 to be scaled down
    until [ "$(${KUBECTL} -n ${NAMESPACE} logs -l ${POD_LABEL_THREE} | grep 'cloudevent(s3): done!' | wc -l)" = "1" ]; do echo "Waiting for chain to finish..."; sleep 2; done

    # Finally, clear-up
    envsubst < ./demo-apps/knative-chaining/chaining.yaml | ${KUBECTL} delete -f -
}
