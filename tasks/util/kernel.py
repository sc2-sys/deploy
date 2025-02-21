from subprocess import run


def get_host_kernel_version():
    # Use a tmp file to not rely on being able to capture our stdout
    tmp_file = "/tmp/svsm_kernel_config"
    run(f"uname -r > {tmp_file}", shell=True, check=True)
    with open(tmp_file, "r") as fh:
        current_kernel_name = fh.read().strip()

    return current_kernel_name
