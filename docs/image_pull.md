## Image Pull

This document describes the different mechanisms to get a container image
inside a cVM in SC2. We _always_ assume that the integrity of container images
must be validated. We also consider the situation in which their confidentiality
must also be preserved.

### Guest Pull

The guest pull mechanism always pulls the container image inside the guest cVM.
This is the default mechanism in CoCo as it allows the most secure, and simplest
deployment: users sign (and encrypt) container images locally, they upload
them to a container registry, pull them inside the cVM, and decrypt them inside
the cVM.

Albeit secure, this mechanism has high performance overheads as the image must
be pulled every single time, precluding any caching benefits.

To mitigate the performance overheads, we can convert the OCI image to a
Nydus image, that supports lazy loading of container data.

### Host Share

The host share mechanism mounts a container image from the host to the guest.
Given that the host is untrusted, this mechanism only works for images that
do not have confidentiality requirements. To maintain integrity, we mount
the image with `dm-verity`, and validate the `dm-verity` device as part of
attestation.

We could mount encrypted images from the host to the guest, but we would be
losing on the de-duplication opportunities in the host.

### Usage

Each image pull mechanism is implemented as a different remote snapshotter
in containerd, all of them based on the [nydus-snapshotter](
https://github.com/containerd/nydus-snapshotter/) plus our modifications.

To switch between different image-pulling mechanisms, you only need to change
the snapshotter mode:

```bash
inv nydus-snapshotter.set-mode [guest-pull,host-share]
```

If you see any snapshotter related issues (either in the `containerd` or the
`nydus-snapshotter` journal logs), you can purge the snapshotters:

```bash
inv nydus-snapshotter.purge
```
