## CoCo Upgrade List

CoCo cuts out new releases often. Here is what you need to do when a new
release comes out.

### Clean-Up Previous Versions

CoCo does not like in-place upgrades. To ensure a smooth upgrade make sure
you first clean-up the previous install:

```bash
inv kuebadm.destroy
sudo rm -rf /opt/kata
sudo rm -rf /opt/confidential-containers
```

### Upgrade Host Kernel

CoCo relies on specific patches for the host kernel. Make sure you upgrade
to the version they point to.

### Upgrade CoCo Version Tag

First, bump the `COCO_VERSION` in `tasks/util/versions.py`. Then work-out
what Kata version is being used, and `cd` into your `kata-containers` source
tree.

### Update Kata and Guest Components

First, rebase `guest-components` to the latest `main` (guest-components is
not tagged anymore, afaict).

Then rebase `sc2-main` and `sc2-baseline` to the new Kata tag (pinned by the
CoCo release). You should also update the `KATA_VERSION` variable in the
versions file.

Once you have pushed the branches to the remote, you will have to re-build
the Kata image:

```bash
inv kata.build --nocache --push
```

### Dry Run

The easies way to test the deployment is to start a new cluster from scratch,
and run some demo functions:

```bash
inv sc2.destroy sc2.deploy --clean
```
