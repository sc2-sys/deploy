<div align="center">
  <h1><code>sc2-deploy</code></h1>

  <p>
    <strong>Deployment and build scripts for
    <a href="https://github.com/sc2-sys/">Serverless Confidential Containers (SC2)</a></strong>
  </p>

  <p>
    <a href="https://github.com/coco-serverless/coco-serverless/actions/workflows/tests.yml"><img src="https://github.com/coco-serverless/coco-serverless/actions/workflows/tests.yml/badge.svg" alt="Integration Tests" /></a>
  </p>
  <hr>
</div>

SC2 is a system to run serverless functions in confidential containers. It
is deployed on a Kubernetes cluster on top of [Knative](
https://knative.dev/docs/), and builds on the [Confidential Containers](
https://github.com/confidential-containers) project.

SC2 currently supports AMD SEV-SNP and Intel TDX as underlying TEE, and requires
deployment on a bare-metal host. Before moving forward, make sure you have a
correct host installation. For SEV-SNP you may use [`snphost ok`](
https://github.com/virtee/snphost.git). Also make sure you have the [right
host kernel](./docs/host_kernel.md).

## Quick Start

To get started with SC2, clone this repository and run:

```bash
# This shell script will auto-detect the installed TEE (TDX or SNP)
source ./bin/workon.sh

# The following will call `sudo` under the hood
inv sc2.deploy [--debug] [--clean]
```

the previous command will: install a single-node k8s cluster with CoCo, install
Knative, and install SC2.

> [!WARNING]
> Deploying SC2 will patch many components of the system like `containerd`,
> `docker`, `nydus-snapshotter`, and `kata`. We recommend installing on a
> fresh host and, potentially, using the `--clean` flag.

You can now check that everything is running by running a simple hello world:

```bash
# Use qemu-tdx-sc2 for TDX
export SC2_RUNTIME_CLASS=qemu-snp-sc2

# Knative demo
envsubst < ./demo-apps/helloworld-knative/service.yaml | kubectl apply -f -
curl $(kubectl -n sc2-demo get ksvc helloworld-knative  --output=custom-columns=URL:.status.url --no-headers)

# Non-Knative demo
envsubst < ./demo-apps/helloworld-py/deployment.yaml | kubectl apply -f -
curl $(kubectl -n sc2-demo get services -o jsonpath='{.items[?(@.metadata.name=="coco-helloworld-py-node-port")].spec.clusterIP}'):8080
```

for more complex applications and workloads, please check our [applications](
https://github.com/sc2-sys/applications) and [experiments](
https://github.com/sc2-sys/experiments).

After you are done using SC2, you may completely remove the cluster by
running:

```bash
inv sc2.destroy [--debug]
```

## Further Reading

For further documentation, you may want to check these other documents:
* [Attestation](./docs/attestation.md) - instructions to set-up remote attestation in SC2.
* [CoCo Upgrade](./docs/upgrade_coco.md) - upgrade the current CoCo version.
* [Guest Components](./docs/guest_components.md) - instructions to patch components inside SC2 guests.
* [Host Kernel](./docs/host_kernel.md) - bump the kernel version in the host.
* [Image Pull](./docs/image_pull.md) - details on the image-pulling mechanisms supported in SC2.
* [K8s](./docs/k8s.md) - documentation about configuring a single-node Kubernetes cluster.
* [Kata](./docs/kata.md) - instructions to build our custom Kata fork and `initrd` images.
* [Key Broker Service](./docs/kbs.md) - docs on using and patching the KBS.
* [Knative](./docs/knative.md) - documentation about Knative, our serverless runtime of choice.
* [Local Registry](./docs/registry.md) - configuring a local registry to store OCI images.
* [OVMF](./docs/ovmf.md) - notes on building OVMF and CoCo's OVMF boot process.
* [SEV](./docs/sev.md) - speicifc documentation to get the project working with AMD SEV machines.
* [Troubleshooting](./docs/troubleshooting.md) - tips to debug when things go sideways.
