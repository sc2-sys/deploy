#!/bin/bash

source ./tests/utils/env.sh

# ------------------------------------------------------------------------------
# Helper functions to set-up the environment
# ------------------------------------------------------------------------------

common_teardown() {
    ${KUBECTL} delete namespace ${SC2_DEMO_NAMESPACE} --ignore-not-found

    # Cautionary inter-test sleep
    sleep ${INTERTEST_SLEEP_SECS}
}

enable_kata_annotation() {
    local annotation="$1"
    local runtime="$2"
    ${INV} kata.enable-annotation ${annotation} --runtime ${runtime}
}

restart_vm_cache() {
    export SC2_RUNTIME_CLASS="qemu-${SC2_TEE}-sc2"

    # Need to pass the environment because the vm-cache script not only uses
    # the SC2_RUNTIME_CLASS env. var, but also others like $HOME or $USER
    sudo -E ${PROJ_ROOT}/vm-cache/target/release/vm-cache restart
}

set_snapshotter_mode() {
    local snapshotter_mode="$1"
    ${INV} nydus-snapshotter.set-mode ${snapshotter_mode}
    ${INV} nydus-snapshotter.purge

    export SC2_SNAPSHOTTER=${snapshotter_mode}

    sleep 1

    # Setting the snapshotter mode changes the config file, so we must restart
    # the vm cache
    restart_vm_cache
}

# ------------------------------------------------------------------------------
# Helper functions clean-up after executions
# ------------------------------------------------------------------------------

cleanup_knative_chaining() {
    # Curl service
    kubectl -n sc2-demo delete -l run=curl pod

    # First service: fan-out
    ${KUBECTL} -n ${SC2_DEMO_NAMESPACE} delete service.serving.knative.dev coco-knative-chaining-one
    ${KUBECTL} -n ${SC2_DEMO_NAMESPACE} delete -l apps.sc2.io/name=knative-chaining-one pod

    # Second service: job sink
    ${KUBECTL} -n ${SC2_DEMO_NAMESPACE} delete JobSink.sinks.knative.dev coco-knative-chaining-two
    ${KUBECTL} -n ${SC2_DEMO_NAMESPACE} delete -l apps.sc2.io/name=knative-chaining-two pod

    # Third service: fan-in
    ${KUBECTL} -n ${SC2_DEMO_NAMESPACE} delete service.serving.knative.dev coco-knative-chaining-three
    ${KUBECTL} -n ${SC2_DEMO_NAMESPACE} delete -l apps.sc2.io/name=knative-chaining-three pod
}

cleanup_knative_hello_world() {
    # Delete resources in order, as it seems to prevent deletion from being stuck
    SERVICE_NAME="helloworld-knative"
    POD_LABEL="apps.sc2.io/name=helloworld-py"
    ${KUBECTL} -n ${SC2_DEMO_NAMESPACE} delete service.serving.knative.dev ${SERVICE_NAME}
    ${KUBECTL} -n ${SC2_DEMO_NAMESPACE} delete -l ${POD_LABEL} pod
}

cleanup_python_hello_world() {
    ${KUBECTL} -n ${SC2_DEMO_NAMESPACE} delete deployment coco-helloworld-py
}

# ------------------------------------------------------------------------------
# Helper functions to run specific workloads
# ------------------------------------------------------------------------------

run_knative_chaining() {
    local runtime_class="$1"
    export SC2_RUNTIME_CLASS="$runtime_class"

    envsubst < ./demo-apps/knative-chaining/chaining.yaml | ${KUBECTL} apply -f -
    sleep 1

    # Curl the channel URL
    ./demo-apps/knative-chaining/curl_cmd.sh

    POD_LABEL="apps.sc2.io/name=knative-chaining-three"

    # Wait for pod 3 to be scaled down
    until [ "$(${KUBECTL} -n ${SC2_DEMO_NAMESPACE} logs -l ${POD_LABEL} | grep 'cloudevent(s3): done!' | wc -l)" = "1" ]; do echo "Waiting for chain to finish..." ; sleep 2; done
}

run_knative_hello_world() {
    local runtime_class="$1"
    export SC2_RUNTIME_CLASS="$runtime_class"

    envsubst < ./demo-apps/helloworld-knative/service.yaml | ${KUBECTL} apply -f -
    sleep 1

    # Get the service URL
    service_name=$(${KUBECTL} -n ${SC2_DEMO_NAMESPACE} get ksvc helloworld-knative  --output=custom-columns=URL:.status.url --no-headers | sed 's|^http://||')
    lb_url=$(${KUBECTL} -n kourier-system get svc kourier -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    curl_out=$(curl -v --retry 3 --header "Host: ${service_name}" ${lb_url})
    [ "${curl_out}" = "Hello World!" ]
}

run_knative_lazy_loading() {
    local runtime_class="$1"
    export SC2_RUNTIME_CLASS="$runtime_class"

    envsubst < ./demo-apps/helloworld-knative-nydus/service.yaml | ${KUBECTL} apply -f -
    sleep 1

    service_name=$(${KUBECTL} -n ${SC2_DEMO_NAMESPACE} get ksvc helloworld-knative  --output=custom-columns=URL:.status.url --no-headers | sed 's|^http://||')
    lb_url=$(${KUBECTL} -n kourier-system get svc kourier -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    curl_out=$(curl -v --retry 3 --header "Host: ${service_name}" ${lb_url})
    [ "${curl_out}" = "Hello World!" ]
}

run_python_hello_world() {
    local runtime_class="$1"
    export SC2_RUNTIME_CLASS="$runtime_class"

    envsubst < ./demo-apps/helloworld-py/deployment.yaml | ${KUBECTL} apply -f -

    export POD_LABEL="apps.sc2.io/name=helloworld-py"

    # Wait for pod to be ready
    until [ "$(${KUBECTL} get pods -n ${SC2_DEMO_NAMESPACE} -l ${POD_LABEL} -o 'jsonpath={..status.conditions[?(@.type=="Ready")].status}')" = "True" ]; do echo "Waiting for pod to be ready..."; sleep 2; done
    sleep 1

    # Get the pod's IP
    service_ip=$(${KUBECTL} get services -n ${SC2_DEMO_NAMESPACE} -o jsonpath='{.items[?(@.metadata.name=="coco-helloworld-py-node-port")].spec.clusterIP}')
    [ "$(curl --retry 3 -X GET ${service_ip}:8080)" = "Hello World!" ]
}

run_python_lazy_loading() {
    local runtime_class="$1"
    export SC2_RUNTIME_CLASS="$runtime_class"

    envsubst < ./demo-apps/helloworld-py-nydus/deployment.yaml | ${KUBECTL} apply -f -

    export POD_LABEL="apps.sc2.io/name=helloworld-py"

    # Wait for pod to be ready
    until [ "$(${KUBECTL} -n ${SC2_DEMO_NAMESPACE} get pods -l ${POD_LABEL} -o 'jsonpath={..status.conditions[?(@.type=="Ready")].status}')" = "True" ]; do echo "Waiting for pod to be ready..."; sleep 2; done
    sleep 1

    # Get the pod's IP
    service_ip=$(${KUBECTL} -n ${SC2_DEMO_NAMESPACE} get services -o jsonpath='{.items[?(@.metadata.name=="coco-helloworld-py-node-port")].spec.clusterIP}')
    [ "$(curl --retry 3 -X GET ${service_ip}:8080)" = "Hello World!" ]
}
