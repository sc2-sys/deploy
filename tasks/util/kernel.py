from subprocess import run


def get_host_kernel_version():
    # Use a tmp file to not rely on being able to capture our stdout
    tmp_file = "/tmp/svsm_kernel_config"
    run(f"uname -r > {tmp_file}", shell=True, check=True)
    with open(tmp_file, "r") as fh:
        current_kernel_name = fh.read().strip()

    return current_kernel_name


def grub_update_default_kernel(kernel_version):
    """
    This method replaces the GRUB_DEFAULT value
    """
    grub_default = f"Advanced options for Ubuntu>Ubuntu, with Linux {kernel_version}"
    result = run(
        f"sudo sed -i 's/^GRUB_DEFAULT=.*/GRUB_DEFAULT=\"{grub_default}\"/' "
        "/etc/default/grub",
        shell=True,
        capture_output=True,
    )
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())

    result = run("sudo update-grub", shell=True, capture_output=True)
    assert result.returncode == 0, print(result.stderr.decode("utf-8").strip())
