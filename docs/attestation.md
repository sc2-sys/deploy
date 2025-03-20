# Attestation in SC2

Attestation is the process of appraising the provisioned TEE and the software
loaded therein. In the TEEs used in SC2, AMD SEV-SNP, and Intel TDX, the
attestation flow is relatively similar: __after__ starting the cVM, the trusted
software in the guest will retrieve an attestation report from the hardware
root-of-trust and will validate it with a [Trustee](
https://github.com/confidential-containers/trustee) deployment that acts as a
relying-party.

The attestation report contains the launch measurement of the cVM, including
the initial software components like OVMF, the initrd, and the guest kernel,
signed to a hardware root-of-trust.

## Trustee

Configuring Trustee to check the launch measurement is not as straightforward
as one may think. At a very high level, Trustee releases secrets/resources
in response to requests iff the request passes an associated _resource policy_
and _attestation policy_.

# TODO: this paragraph may not be true?
This policy may (or may not) demand that the request presents a valid launch
measurement, matching a user-provided one. As a consequence: no secret/resource
means no policy checking.

To provision secrets and resources to Trustee, we can use a client tool called
the KBC. To make matters worse, however, the attestation code in guest-components
(which also uses the KBC) will _only_ request a very specific resource. We
explain next how to configure Trustee to achieve three different goals:

### Launch Measurement Verification

### Image Signature

### Image Encryption

## SEV-SNP Attestation

## SEV(-ES) Attestation

In SEV-ES the attestation (or pre-attestation) is driven by the **host**, and
happens before guest boot.

The host also facilitates the establishment of a secure channel between the
guest owner and the PSP.

As part of the pre-attestation, the host generates a launch measurement which
contains:
- Platform Information
- Launch Digest:
  - Hash of VM firmware
  - Initial vCPU State (only for SEV-ES)

The contents of the initial launch measurement are provisioned by the host and
measured by the PSP. Thus, they cannot contain any secrets.

Once the launch measurement is finished, the PSP uses the secure channel to
communicate the measurement to the guest owner, which will decide whether to
accept the measurement or not.

If the measurement is accepted, the guest owner can provision some unique
secrets and the VM can be booted.

## SEV-ES Direct Boot Process

To boot an SEV VM with CoCo we use a special VM firmware. In particular, we
take advantage of specific SEV support in OVMF.

The [AMD SEV package in OVMF](https://github.com/tianocore/edk2/blob/master/OvmfPkg/AmdSev/AmdSevX64.dsc)
sets aside some space in the firmware binary for storing the hashes of the
`initrd`, the kernel, and the kernel command line. When QEMU boots an SEV VM,
it hashes each of these components and injects the hashes into the firmware
bianry.

This means that when the host is provisioning the initial VM state, and the
PSP is measuring it, the measurement will be tied to a specific `initrd`,
kernel, and kernel command line, hash.

Then, we boot the VM directly from the `initrd` which contains the Kata Agent
as the `/sbin/init` process. In the `initrd` we also have other
[`guest-components`](https://github.com/confidential-containers/guest-components)
which include the `attestation-agent`, that will talk to the guest owner
to continue provisioning secrets to the guest after boot.
