from base64 import b64encode
from json import dumps as json_dumps
from os import makedirs
from os.path import join
from pymysql import connect as mysql_connect
from pymysql.cursors import DictCursor
from re import search as re_search, sub as re_sub
from subprocess import run
from tasks.util.cosign import COSIGN_PUB_KEY
from tasks.util.env import KATA_CONFIG_DIR, PROJ_ROOT, get_node_url
from tasks.util.toml import read_value_from_toml, update_toml
from tasks.util.sev import get_launch_digest

# TODO: think about this, where does it make sense to have the trustee?
# TODO: probably the less bad solution is to have it as a submodule?
TRUSTEE_DIR = join(PROJ_ROOT, "..", "trustee")
# WARNING: this resource path depends on the KBS' `server` service working
# directory. The server expects the `resources` directory to be in:
# /<working_dir>/resources
SIMPLE_KBS_RESOURCE_PATH = join(TRUSTEE_DIR, "resources")
SIMPLE_KBS_KEYS_RESOURCE_PATH = join(SIMPLE_KBS_RESOURCE_PATH, "keys")

DEFAULT_LAUNCH_POLICY_ID = 10

# ------------------------------------------------------------------------------
# Key Broker Service
# ------------------------------------------------------------------------------

KBS_ROOT = join(TRUSTEE_DIR, "kbs")
KBS_CONFIG_DIR = join(KBS_ROOT, "config")
KBS_HOST_PORT = "50002"


def get_kbs_ip():
    """
    Get the IP where the KBS is deployed. Note that this IP must be reachable
    from the guest, so it cannot be localhost even if Trustee is deployed
    locally.
    """
    # TODO: change when we support deploying the KBS remotely, elsewhere
    return get_node_url()


# ------------------------------------------------------------------------------
# Guest Attestation
# ------------------------------------------------------------------------------


def get_trustee_kernel_parameters(kernel_params, mode):
    kbs_ip = get_kbs_ip()

    # Regex patterns for the key-value pairs
    guest_api_pattern = r"\bagent\.guest_components_rest_api=resource\b"
    aa_kbc_pattern = r"\bagent\.aa_kbc_params=cc_kbc::http:\/\/[^ ]+:\d+\b"

    # Add/remove the kernel parameters from the given white-separated key=val
    # string, without modifying other parameters
    if mode == "off":
        # Remove the key-value pairs if they exist
        kernel_params = re_sub(guest_api_pattern, "", kernel_params)
        kernel_params = re_sub(aa_kbc_pattern, "", kernel_params)
    else:
        # Add the key-value pairs with the specified IP if they are missing
        if not re_search(guest_api_pattern, kernel_params):
            kernel_params += " agent.guest_components_rest_api=resource"
        if not re_search(aa_kbc_pattern, kernel_params):
            kernel_params += (
                f" agent.aa_kbc_params=cc_kbc::http://{kbs_ip}:{KBS_HOST_PORT}"
            )

    kernel_params = re_sub(r"\s+", " ", kernel_params).strip()
    return kernel_params


def do_set_guest_attestation_mode(mode, runtime):
    """
    This method toggles the guest attestation feature. If enabled, after
    booting and before pulling the container image, the attestation agent in
    the guest will send its attestation report to Trustee, which will apply
    the attestation policy.

    Note that this can also be set by adding an annotation to the pod:
    io.katacontainers.config.hypervisor.kernel_params:
      "agent.guest_components_rest_api=resource
       agent.aa_kbc_params=cc_kbc::http://{trustee_kbs_ip}:{trustee_kbs_port}"
    """
    supported_modes = ["on", "off"]
    if mode not in supported_modes:
        print(f"ERROR: unsupported guest attestation mode: {mode}")
        print(f"ERROR: must be one in : {supported_modes}")
        exit(1)

    conf_file_path = join(KATA_CONFIG_DIR, f"configuration-{runtime}.toml")
    kernel_params = read_value_from_toml(
        conf_file_path, "hypervisor.qemu.kernel_params"
    )
    updated_kernel_params = get_trustee_kernel_parameters(kernel_params, mode)

    updated_toml_str = """
    [hypervisor.qemu]
    kernel_params = "{updated_kernel_params}"
    """.format(
        updated_kernel_params=updated_kernel_params
    )
    update_toml(conf_file_path, updated_toml_str)


# ------------------------------------------------------------------------------
# Image Signature and Encryption
# ------------------------------------------------------------------------------

# TODO

# ------------------------------------------------------------------------------
# Legacy Code
# ------------------------------------------------------------------------------

# --------
# Signature Verification Policy
# --------

# This is the policy id that the kata-agent asks for when required to validate
# image signatures. It is hardcoded somewhere in the agent code
SIGNATURE_POLICY_STRING_ID = "default/security-policy/test"

NO_SIGNATURE_POLICY = "no-signature-policy"
SIGNATURE_POLICY_NONE = "none"
SIGNATURE_POLICY_VERIFY = "verify"
ALLOWED_SIGNATURE_POLICIES = [SIGNATURE_POLICY_NONE, SIGNATURE_POLICY_VERIFY]
SIGNATURE_POLICY_NONE_JSON = """{
    "default": [{"type": "insecureAcceptAnything"}],
    "transports": {}
}
"""
SIGNATURE_POLICY_VERIFY_JSON = {
    "default": [{"type": "reject"}],
    "transports": {"docker": {}},
}


def get_kbs_db_ip():
    docker_cmd = "docker network inspect simple-kbs_default | jq -r "
    docker_cmd += (
        "'.[].Containers[] | select(.Name | test(\"simple-kbs[_-]db.*\")).IPv4Address'"
    )
    db_ip = (
        run(docker_cmd, shell=True, capture_output=True)
        .stdout.decode("utf-8")
        .strip()[:-3]
    )
    return db_ip


def connect_to_kbs_db():
    """
    Get a working MySQL connection to the KBS DB
    """
    # Get the database IP
    db_ip = get_kbs_db_ip()

    # Connect to the database
    connection = mysql_connect(
        host=db_ip,
        user="kbsuser",
        password="kbspassword",
        database="simple_kbs",
        cursorclass=DictCursor,
    )

    return connection


def clear_kbs_db(skip_secrets=False):
    """
    Clear the contents of the KBS DB
    """
    connection = connect_to_kbs_db()
    with connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE from policy")
            cursor.execute("DELETE from resources")
            if not skip_secrets:
                cursor.execute("DELETE from secrets")

        connection.commit()


def set_launch_measurement_policy():
    """
    This method configures and sets the launch measurement policy
    """
    # Get the launch measurement
    ld = get_launch_digest("sev")
    ld_b64 = b64encode(ld).decode()

    # Create a policy associated to this measurement in the KBS DB
    connection = connect_to_kbs_db()
    with connection:
        with connection.cursor() as cursor:
            sql = "INSERT INTO policy VALUES ({}, ".format(DEFAULT_LAUNCH_POLICY_ID)
            sql += "'[\"{}\"]', '[]', 0, 0, '[]', now(), NULL, 1)".format(ld_b64)
            cursor.execute(sql)

        connection.commit()


def create_kbs_resource(
    resource_id,
    resource_kbs_path,
    resource_contents,
    resource_launch_policy_id=DEFAULT_LAUNCH_POLICY_ID,
):
    """
    Create a KBS resource for the kata-agent to consume

    Each KBS resource is identified by a resource ID. Each KBS resource has
    a resource path, where the actual resource lives. In addition, each
    each resource is associated to a launch policy, that checks that the FW
    digest is as expected.

    KBS resources are stored in a `resources` directory in the same **working
    directory** from which we call the KBS binary. This value can be checked
    in the simple KBS' docker-compose.yml file. The `resource_path` argument is
    a relative directory from the base `resources` directory.
    """
    makedirs(SIMPLE_KBS_RESOURCE_PATH, exist_ok=True)

    # First, insert the resource in the SQL database
    connection = connect_to_kbs_db()
    with connection:
        with connection.cursor() as cursor:
            sql = "INSERT INTO resources VALUES(NULL, NULL, "
            sql += "'{}', '{}', {})".format(
                resource_id, resource_kbs_path, resource_launch_policy_id
            )
            cursor.execute(sql)

        connection.commit()

    # Second, dump the resource contents in the specified resource path
    with open(join(SIMPLE_KBS_RESOURCE_PATH, resource_kbs_path), "w") as fh:
        fh.write(resource_contents)


def create_kbs_secret(
    secret_id, secret_contents, resource_launch_policy_id=DEFAULT_LAUNCH_POLICY_ID
):
    """
    Create a KBS secret for the kata-agent to consume
    """
    # First, insert the resource in the SQL database
    connection = connect_to_kbs_db()
    with connection:
        with connection.cursor() as cursor:
            sql = "INSERT INTO secrets VALUES(NULL, "
            sql += "'{}', '{}', {})".format(
                secret_id, secret_contents, resource_launch_policy_id
            )
            cursor.execute(sql)

        connection.commit()


def validate_signature_verification_policy(signature_policy):
    """
    Validate that a given signature policy is supported
    """
    if signature_policy not in ALLOWED_SIGNATURE_POLICIES:
        print(
            "--signature-policy must be one in: {}".format(ALLOWED_SIGNATURE_POLICIES)
        )
        raise RuntimeError("Disallowed signature policy: {}".format(signature_policy))


def populate_signature_verification_policy(signature_policy, policy_details=None):
    """
    Given a list of tuples containing an image name, and the resource id of the
    key used to sign it, return the JSON string containing the signature
    verification policy
    """
    if signature_policy == SIGNATURE_POLICY_NONE:
        return SIGNATURE_POLICY_NONE_JSON

    policy = SIGNATURE_POLICY_VERIFY_JSON
    for image_name, signing_key_resource_id in policy_details:
        policy["transports"]["docker"][image_name] = [
            {
                "type": "sigstoreSigned",
                "keyPath": "kbs:///{}".format(signing_key_resource_id),
            }
        ]

    return json_dumps(policy)


def provision_launch_digest(
    images_to_sign, signature_policy=SIGNATURE_POLICY_NONE, clean=False
):
    """
    For details on this method check the main entrypoint task with the same
    name in ./tasks/kbs.py.
    """
    validate_signature_verification_policy(signature_policy)

    if clean:
        clear_kbs_db()

    # First, we provision a launch digest policy that only allows to
    # boot confidential VMs with the launch measurement that we have
    # just calculated. We will associate signature verification and
    # image encryption policies to this launch digest policy.
    set_launch_measurement_policy()

    # To make sure the launch policy is enforced, we must enable
    # signature verification. This means that we also need to provide a
    # signature policy. This policy has a constant string identifier
    # that the kata agent will ask for (default/security-policy/test),
    # which points to a config file that specifies how to validate
    # signatures
    resource_path = "signature_policy_{}.json".format(signature_policy)

    if signature_policy == SIGNATURE_POLICY_NONE:
        # If we set a `none` signature policy, it means that we don't
        # check any signatures on the pulled container images (still
        # necessary to set the policy to check the launch measurment)
        policy_json_str = populate_signature_verification_policy(signature_policy)
    else:
        # The verify policy, checks that the image has been signed
        # with a given key. As everything in the KBS, the key
        # we give in the policy is an ID for another resource.
        # Note that the following resource prefix is NOT required
        # (i.e. we could change it to keys/cosign/1 as long as the
        # corresponding resource exists)
        signing_key_resource_id = "default/cosign-key/1"
        policy_details = [
            [image_tag, signing_key_resource_id] for image_tag in images_to_sign
        ]
        policy_json_str = populate_signature_verification_policy(
            signature_policy,
            policy_details,
        )

        # Create a resource for the signing key
        with open(COSIGN_PUB_KEY) as fh:
            create_kbs_resource(signing_key_resource_id, "cosign.pub", fh.read())

    # Finally, create a resource for the image signing policy. Note that the
    # resource ID for the image signing policy is hardcoded in the kata agent
    # (particularly in the attestation agent)
    create_kbs_resource(SIGNATURE_POLICY_STRING_ID, resource_path, policy_json_str)
