from invoke import task
from json import loads as json_loads
from os import makedirs
from os.path import join
from tasks.util.env import PROJ_ROOT
from subprocess import run

ANSIBLE_ROOT = join(PROJ_ROOT, "ansible")
ANSIBLE_INVENTORY_DIR = join(ANSIBLE_ROOT, "inventory")
ANSIBLE_INVENTORY_FILE = join(ANSIBLE_INVENTORY_DIR, "vms.ini")

# TODO: request creating a new resource group named sc2
AZURE_RESOURCE_GROUP = "faasm"

AZURE_SNP_VM_ADMIN = "sc2"
AZURE_SNP_VM_IMAGE = (
    "/CommunityGalleries/cocopreview-91c44057-c3ab-4652-bf00-9242d5a90170/"
    "Images/ubu2204-snp-host-upm/Versions/latest"
)
AZURE_SNP_VM_LOCATION = "eastus"
AZURE_SNP_VM_OS_DISK_SIZE = 64
AZURE_SNP_VM_SSH_PRIV_KEY = "~/.ssh/id_rsa"
AZURE_SNP_VM_SSH_PUB_KEY = "~/.ssh/id_rsa.pub"
AZURE_SNP_VM_SKU = "Standard_DC8as_cc_v5"

# Specifies order in which to delete resource types
RESOURCE_TYPE_PRECEDENCE = [
    "Microsoft.Network/networkInterfaces",
    "Microsoft.Network/networkSecurityGroups",
    "Microsoft.Network/virtualNetworks",
    "Microsoft.Network/publicIpAddresses",
]

# -----------------------------------------------------------------------------
# Azure Functions
# -----------------------------------------------------------------------------


def build_ssh_command(ip_addr):
    return f"ssh -A -i {AZURE_SNP_VM_SSH_PRIV_KEY} {AZURE_SNP_VM_ADMIN}@{ip_addr}"


def get_ip(name):
    cmd = [
        "az vm list-ip-addresses",
        "-n {}".format(name),
        "-g {}".format(AZURE_RESOURCE_GROUP),
    ]

    cmd = " ".join(cmd)
    res = run(cmd, shell=True, capture_output=True)

    res = json_loads(res.stdout.decode("utf-8"))
    vm_info = res[0]["virtualMachine"]
    return vm_info["network"]["publicIpAddresses"][0]["ipAddress"]


def vm_op(op, name, extra_args=None, capture=False):
    print("Performing {} on {}".format(op, name))

    cmd = [
        "az vm {}".format(op),
        "--resource-group {}".format(AZURE_RESOURCE_GROUP),
        "--name {}".format(name),
    ]

    if extra_args:
        cmd.extend(extra_args)

    cmd = " ".join(cmd)
    print(cmd)

    if capture:
        res = run(cmd, shell=True, capture_stdout=True)
        return res.stdout.decode("utf-8")
    else:
        run(cmd, shell=True, check=True)


def delete_resource(name, resource_type):
    print(f"Deleting resource {name}")

    cmd = (
        f"az resource delete --resource-group {AZURE_RESOURCE_GROUP} "
        f"--name {name} --resource-type {resource_type}"
    )
    run(cmd, check=True, shell=True)


def delete_resources(resources):
    print("Deleting {} resources".format(len(resources)))

    deleted_resources = list()

    # Prioritise certain types
    for t in RESOURCE_TYPE_PRECEDENCE:
        to_delete = [r for r in resources if r["type"] == t]

        if to_delete:
            print("Prioritising {} resources of type {}".format(len(to_delete), t))

        for r in to_delete:
            delete_resource(r["name"], r["type"])
            deleted_resources.append(r["id"])

    remaining = [r for r in resources if r["id"] not in deleted_resources]
    for r in remaining:
        delete_resource(r["name"], r["type"])


def list_all(azure_cmd, prefix=None):
    cmd = f"az {azure_cmd} list --resource-group {AZURE_RESOURCE_GROUP}"
    res = run(cmd, shell=True, capture_output=True)
    res = json_loads(res.stdout.decode("utf-8"))

    if prefix:
        res = [v for v in res if v["name"].startswith(prefix)]

    return res


# -----------------------------------------------------------------------------
# Ansible functions
# -----------------------------------------------------------------------------


def ansible_prepare_inventory(prefix):
    """
    Create ansbile inventory for VMs
    """
    all_vms = list_all("vm", prefix)

    if len(all_vms) == 0:
        print(f"Did not find any VMs matching prefix {prefix}")
        raise RuntimeError("No VMs found with prefix")

    print("Generating inventory for {} VMs".format(len(all_vms)))

    # Sort VMs based on name to ensure consistent choice of main
    all_vms = sorted(all_vms, key=lambda d: d["name"])

    # Get all IPs
    for vm in all_vms:
        vm["public_ip"] = get_ip(vm["name"])

    makedirs(ANSIBLE_INVENTORY_DIR, exist_ok=True)

    # One group for all VMs, one for main, one for workers
    lines = ["[all]"]
    for v in all_vms:
        # Include VM name for debugging purposes
        lines.append(
            "{} ansible_host={} ansible_user={}".format(
                v["name"], v["public_ip"], AZURE_SNP_VM_ADMIN
            )
        )

    file_content = "\n".join(lines)

    print("Contents:\n")
    print(file_content)

    with open(ANSIBLE_INVENTORY_FILE, "w") as fh:
        fh.write(file_content)
        fh.write("\n")


# -----------------------------------------------------------------------------
# Entrypoint tasks
# -----------------------------------------------------------------------------


@task
def deploy(ctx):
    """
    Deploy SC2 on an SNP-enabled VM on Azure
    """
    vm_name = "sc2-snp-test"
    az_cmd = (
        f"az vm create -g {AZURE_RESOURCE_GROUP} -n {vm_name} "
        f"--location {AZURE_SNP_VM_LOCATION} --admin-username {AZURE_SNP_VM_ADMIN} "
        f"--image {AZURE_SNP_VM_IMAGE} --accept-term --size {AZURE_SNP_VM_SKU} "
        f"--ssh-key-value {AZURE_SNP_VM_SSH_PUB_KEY} --accelerated-networking true "
        f"--os-disk-size-gb {AZURE_SNP_VM_OS_DISK_SIZE}"
    )
    run(az_cmd, shell=True, check=True)

    ansible_prepare_inventory(vm_name)

    vm_playbook = join(ANSIBLE_ROOT, "vm.yaml")
    run(
        f"ansible-playbook -i {ANSIBLE_INVENTORY_FILE} {vm_playbook}",
        shell=True,
        check=True,
    )


@task
def destroy(ctx, vm_name="sc2-snp-test"):
    # First delete the VM
    vm_op("delete", vm_name, extra_args=["--yes"])

    # Delete all other resources associated with it that may be left
    all_resources = list_all("resource", prefix=vm_name)
    delete_resources(all_resources)


@task
def ssh(ctx, name="sc2-snp-test"):
    """
    Prints SSH information for given VM
    """
    ip_addr = get_ip(name)
    print("--- SSH command ---\n")
    print(build_ssh_command(ip_addr))

    print("\n--- SSH config ---")
    print(
        """
# SC2 Azure SNP VM
Host {}
HostName {}
User {}
ForwardAgent yes
        """.format(
            name, ip_addr, AZURE_SNP_VM_ADMIN
        )
    )
