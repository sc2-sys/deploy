#!/bin/bash

./bin/kubectl -n sc2-demo run curl --image=curlimages/curl --restart=Never -- -X POST -v \
   -H "content-type: application/json"  \
   -H "ce-specversion: 1.0" \
   -H "ce-source: cli" \
   -H "ce-type: http://one-to-two-kn-channel.sc2-demo.svc.cluster.local" \
   -H "ce-id: 1" \
   -d '{"details":"ChannelDemo"}' \
   http://ingress-to-one-kn-channel.sc2-demo.svc.cluster.local

