from invoke import task
from subprocess import run
from tasks.util.docker import is_ctr_running
from tasks.util.env import KATA_WORKON_CTR_NAME


@task
def cli(ctx):
    """
    Get a CLI container for guest-components (using Kata's work-on)

    The guest-components source code is included in the Kata work-on image,
    and mounted when we start a kata CLI. This method here is just a helper
    to get us in the right working-directory.
    """
    if not is_ctr_running(KATA_WORKON_CTR_NAME):
        print("ERROR: start the kata work-on container before getting a gc CLI")
        print("ERROR: consider running: inv kata.cli")
        return

    # This path is hardcoded in ./docker/kata.dockerfile
    gc_workdir = "/git/sc2-sys/guest-components"
    run(f"docker exec -w {gc_workdir} -it {KATA_WORKON_CTR_NAME} bash", shell=True, check=True)
