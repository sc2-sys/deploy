from json import loads as json_loads
from os.path import exists, join
from subprocess import CalledProcessError, run
from tasks.util.docker import build_image
from tasks.util.env import GHCR_URL, GITHUB_ORG, PROJ_ROOT
from tasks.util.versions import CONTAINERD_VERSION
from time import sleep, time

CONTAINERD_IMAGE_TAG = (
    join(GHCR_URL, GITHUB_ORG, "containerd") + f":{CONTAINERD_VERSION}"
)


def build_containerd_image(nocache, push, debug=True):
    build_image(
        CONTAINERD_IMAGE_TAG,
        join(PROJ_ROOT, "docker", "containerd.dockerfile"),
        nocache=nocache,
        push=push,
        debug=debug,
    )


def is_containerd_active():
    out = (
        run("sudo systemctl is-active containerd", shell=True, capture_output=True)
        .stdout.decode("utf-8")
        .strip()
    )
    return out == "active"


def restart_containerd(debug=False):
    """
    Utility function to gracefully restart the containerd service
    """
    run("sudo service containerd restart", shell=True, check=True)

    # First wait for systemd to report containerd as active
    while not is_containerd_active():
        if debug:
            print("Waiting for containerd to be active...")

        sleep(2)

    # Then make sure we can dial the socket
    wait_for_containerd_socket()


def get_journalctl_containerd_logs(timeout_mins=1):
    """
    Get the journalctl logs for containerd

    We dump them to a temporary file to prevent the Popen output from being
    clipped (or at least remove the chance of it being so)
    """
    tmp_file = "/tmp/journalctl.log"
    journalctl_cmd = "sudo journalctl -xeu containerd --no-tail "
    journalctl_cmd += '--since "{} min ago" -o json > {}'.format(timeout_mins, tmp_file)
    run(journalctl_cmd, shell=True, check=True)

    with open(tmp_file, "r") as fh:
        lines = fh.readlines()

    return lines


def get_event_from_containerd_logs(
    event_name, event_id, num_events, extra_event_id=None, timeout_mins=1
):
    """
    Get the last `num_events` events in containerd logs that correspond to
    the `event_name` for sandbox/pod/container id `event_id`
    """
    # Parsing from `journalctl` is slightly hacky, and prone to spurious
    # errors. We put a lot of assertions here to make sure that the timestamps
    # we read are the adequate ones, thus we allow some failures and retry
    num_repeats = 3
    backoff_secs = 3
    for i in range(num_repeats):
        try:
            out = get_journalctl_containerd_logs(timeout_mins)

            event_json = []
            for o in out:
                o_json = json_loads(o)
                if (
                    o_json is None
                    or "MESSAGE" not in o_json
                    or o_json["MESSAGE"] is None
                ):
                    # Sometimes, after resetting containerd, some of the
                    # journal messages won't have a "MESSAGE" in it, so we skip
                    # them
                    continue
                try:
                    if (
                        event_name in o_json["MESSAGE"]
                        and event_id in o_json["MESSAGE"]
                    ):
                        if (
                            extra_event_id is None
                            or extra_event_id in o_json["MESSAGE"]
                        ):
                            event_json.append(o_json)
                except TypeError as e:
                    print(o_json)
                    print(e)
                    raise e

            assert (
                len(event_json) >= num_events
            ), "Not enough events in log: {} !>= {}".format(len(event_json), num_events)

            return event_json[-num_events:]
        except AssertionError as e:
            print(e)
            print(
                "WARNING: Failed getting event {} (id: {}) (attempt {}/{})".format(
                    event_name,
                    event_id,
                    i + 1,
                    num_repeats,
                )
            )
            sleep(backoff_secs)
            continue


def get_ts_for_containerd_event(
    event_name,
    event_id,
    lower_bound=None,
    extra_event_id=None,
    timeout_mins=1,
):
    """
    Get the journalctl timestamp for one event in the containerd logs
    """
    event_json = get_event_from_containerd_logs(
        event_name, event_id, 1, extra_event_id=None, timeout_mins=timeout_mins
    )[0]
    ts = int(event_json["__REALTIME_TIMESTAMP"]) / 1e6

    if lower_bound is not None:
        assert (
            ts > lower_bound
        ), "Provided timestamp smaller than lower bound: {} !> {}".format(
            ts, lower_bound
        )

    return ts


def get_start_end_ts_for_containerd_event(
    event_name,
    event_id,
    lower_bound=None,
    extra_event_id=None,
    timeout_mins=1,
):
    """
    Get the start and end timestamps (in epoch floating seconds) for a given
    event from the containerd journalctl logs
    """
    event_json = get_event_from_containerd_logs(
        event_name,
        event_id,
        2,
        extra_event_id=extra_event_id,
        timeout_mins=timeout_mins,
    )

    start_ts = int(event_json[-2]["__REALTIME_TIMESTAMP"]) / 1e6
    end_ts = int(event_json[-1]["__REALTIME_TIMESTAMP"]) / 1e6

    assert end_ts > start_ts, "End and start timestamp not in order: {} !> {}".format(
        end_ts, start_ts
    )

    if lower_bound is not None:
        assert (
            start_ts > lower_bound
        ), "Provided timestamp smaller than lower bound: {} !> {}".format(
            start_ts, lower_bound
        )

    return start_ts, end_ts


def get_all_events_in_between(
    start_event, start_event_id, end_event, end_event_id, event_to_find
):
    """
    Return all events with `event_to_find` in their message that happen between
    events with `start_event` and `start_event_id` in their message and
    `end_event` and `end_event_id`.
    """
    out = get_journalctl_containerd_logs()
    events_json = []

    # First, find the sub-list containing all events between our begining
    # and end event
    start_event_idx = -1
    end_event_idx = -1
    for idx, o in enumerate(out):
        o_json = json_loads(o)
        if o_json is None or "MESSAGE" not in o_json or o_json["MESSAGE"] is None:
            continue

        if start_event in o_json["MESSAGE"] and start_event_id in o_json["MESSAGE"]:
            start_event_idx = idx

        if end_event in o_json["MESSAGE"] and end_event_id in o_json["MESSAGE"]:
            end_event_idx = idx

    # Sanity check the indexes
    assert start_event_idx >= 0, "Could not find start event: {} (id: {})".format(
        start_event, start_event_id
    )
    assert end_event_idx >= 0, "Could not find end event: {} (id: {})".format(
        end_event, end_event_id
    )
    assert end_event_idx > start_event_idx, "End event earlier than start event"

    # Then filter the sub-list for the events we are interested in
    for o in out[start_event_idx:end_event_idx]:
        o_json = json_loads(o)
        if event_to_find in o_json["MESSAGE"]:
            events_json.append(o_json)

    return events_json


def wait_for_containerd_socket():
    timeout = 10
    interval = 1
    socket_path = "/run/containerd/containerd.sock"

    # Socket is root-owned, so we need to be careful when probing it
    socket_test_script = f"""
import socket
try:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect('{socket_path}')
except Exception as e:
    exit(1)
exit(0)
"""
    start_time = time()
    while time() - start_time < timeout:
        if exists(socket_path):
            try:
                run(
                    f'sudo python3 -c "{socket_test_script}"',
                    shell=True,
                    check=True,
                )

                return
            except CalledProcessError:
                pass

        sleep(interval)

    raise RuntimeError("Error dialing containerd socket!")
