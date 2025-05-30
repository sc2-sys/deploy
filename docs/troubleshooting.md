# Troubleshooting

In this document we include a collection of tips to help you debug the system
in case something is not working as expected.

## K8s Monitoring with K9s

Gaining visibility into the state of a Kubernetes cluster is hard. Thus we can
not stress enough how useful `k9s` is to debug what is going on.

We strongly recommend you using it, you may install it with:

```bash
inv k9s.install
export KUBECONFIG=$(pwd)/.config/kubeadm_kubeconfig
k9s
```

## Enabling debug logging in the system journal

Another good observability tool are the journal logs. Both `containerd` and
`kata-agent` send logs to the former's systemd journal log. You may inspect
the logs using:

```bash
sudo journalctl -xeu containerd
```

To enable debug logging you may run:

```bash
inv containerd.set-log-level [debug,info]
inv kata.set-log-level [debug,info]
```

naturally, run the commands again with `info` to reset the original log level.

## Nuking the whole cluster

When things really go wrong, resetting the whole cluster is usually a good way
to get a clean start:

```bash
inv kubeadm.destroy kubeadm.create
```

If you want a really clean start, you can re-install cotnainerd and all the
`k8s` tooling:

```bash
inv kubeadm.destroy
inv containerd.build containerd.install
inv k8s.install --clean
inv kubeadm.create
```

## Known Issues

### Cluster Creation Issues

Sometimes after rebboot, `inv kubeadm.create` failes because it cannot start
the `kubelet` process. If you check the `kubelet` logs (
`sudo journalctl -xeu kubelet`) and you see that it failed to start due to
swapping issues you must disable swap:

```bash
sudo swapoff -a
```

### Host Issues

If you encounter an error from `containerd` failing to create any pods with
a message similar to the following:

```
Failed to create pod sandbox: rpc error: code = Unknown desc = failed to create containerd task: failed to create shim task: Creating watcher returned error too many open files: unknown
```

then you need to increase the host kerenel's parameters:

```bash
sudo sysctl fs.inotify.max_user_instances=1280
sudo sysctl fs.inotify.max_user_watches=655360
```

### Container Creation Issues

If the container fails to start with an error along the lines of:

```bash
 No such file or directory (os error 2) while canonicalizing /run/kata-containers/image/layers/...
```

you may have a combination of an old guest components and/or nydus snapshotter.
To fix the issue make sure that:

you are using the latest nydus snapshotter:

```bash
inv nydus.install
```

you are using the latest guest components:

```bash
inv kata.build kata.replace-agent
```

you have nuked the containerd and nydus caches:

```bash
rm -rf /var/lib/containerd
rm -rf /var/lib/cotnainerd-nydus
```

then restart `containerd` and `nydus`:

```bash
sudo service containerd restart
sudo service nydus-snapshotter restart
```

### Nydus Caching Issue

For images with the same digest, nydus seems to cache the image tag. Meaning
that if you re-tag the same image, nydus will still try to pull the old tag.

To fix this, delete the duplicated image tags (i.e. tags with the same digest)
using something like:

```bash
sudo ctr -n k8s.io image rm $(sudo ctr -n k8s.io image ls | grep coco | awk '{print $1}')
```

### Nydus Clean-Up Issue

If you encounter a `ContainerCreating` error with an error message along the
lines of:

```
failed to extract layer sha256:1e604deea57dbda554a168861cff1238f93b8c6c69c863c43aed37d9d99c5fed: failed to get reader from content store: content digest sha256:9fa9226be034e47923c0457d916aa68474cdfb23af8d4525e9baeebc4760977a: not found
```

you may not be setting the right annotation in the pod:

```
io.containerd.cri.runtime-handler: kata-qemu-...
```

A temporary fix to get the pod running is to manually fetch the content but, as
said above, the annotation should take care of this.

```bash
ctr -n k8s.io content fetch ${IMAGE_NAME}
```

### Rootfs Mount Issue

Sometimes, if we are mixing and matching different snapshotters, we may run
into the following error:

```
Failed to create pod sandbox: rpc error: code = Unknown desc = failed to create containerd task: failed to create shim task: failed to mount /run/kata-containers/shared/containers/0a583f0691d78e2036425f99bdac8e03302158320c1c55a5c6482cae7e729009/rootfs to /run/kata-containers/0a583f0691d78e2036425f99bdac8e03302158320c1c55a5c6482cae7e729009/rootfs, with error: ENOENT: No such file or directory
```

this is because the pause image bundle has not been unpacked correctly. Note
that the pause image bundle is unpacked into the `/run/kata-containers/shared`
directory, and then mounted into the `/run/kata-containers/<cid>` one.

This usually happens when containerd believes that we already have the pause
image, so we do not need to pull it. This prevents the snapshotter from
generating the respective Kata virtual volumes.

As a rule of thumb, a good fix is to remove all images involved in the app
from the content store, and purge snapshotter caches:

```bash
sudo crictl rmi <hash>
inv nydus-snapshotter.purge
```
