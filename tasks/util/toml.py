from re import findall
from os import getuid, getgid, remove, stat
from os.path import basename, join
from subprocess import run
from toml import (
    dump as toml_dump,
    load as toml_load,
    loads as toml_load_from_string,
)


def merge_dicts_recursively(dict_a, dict_b):
    """
    Merge dict_b into dict_a recursively (allowing nested dictionaries)

    Invariant: dict_b is a subset of dict_a
    """
    # If A is not a dict return
    if not isinstance(dict_a, dict):
        raise RuntimeError("Unreachable: A should be a dict!")
        return

    if not isinstance(dict_b, dict):
        raise RuntimeError("Unreachable: B should be a dict!")
        return

    for k in dict_b:
        if k in dict_a:
            if isinstance(dict_a[k], dict) and isinstance(dict_b[k], dict):
                # If an entry is a tree in both TOMLs, recurse
                merge_dicts_recursively(dict_a[k], dict_b[k])
            elif not isinstance(dict_a[k], dict):
                # If dict_a[k] is not a dict, it means we have reached a leaf
                # of A, shared with B. In this case we always copy the subtree
                # from B (irrespective of whether it is a subtree or not)
                dict_a[k] = dict_b[k]
            else:
                # This situation should be unreachable
                raise RuntimeError("Unreachable!")
        else:
            # If the key is not in the to-be merged dict, we want to copy all
            # the sub-tree
            dict_a[k] = dict_b[k]


def update_toml(toml_path, updates_toml, requires_root=True):
    """
    Helper method to update entries in a TOML file

    Updating a TOML file is very frequent in the CoCo environment, particularly
    `root` owned TOML files. So this utility method aims to make that easier.
    Parameters:
    - toml_path: path to the TOML file to modify
    - updates_toml: TOML string with the required updates (simplest way to
                    express arbitrarily complex TOML files)
    - requires_root: whether the TOML file is root-owned (usually the case)
    """
    if requires_root:
        new_toml_file_path = join("/tmp", basename(toml_path) + "-read")
        run(f"sudo cp {toml_path} {new_toml_file_path}", shell=True, check=True)
        run(
            "sudo chown {}:{} {}".format(getuid(), getgid(), new_toml_file_path),
            shell=True,
            check=True,
        )

        conf_file = toml_load(new_toml_file_path)
        run(f"sudo rm {new_toml_file_path}", shell=True, check=True)
    else:
        conf_file = toml_load(toml_path)

    merge_dicts_recursively(conf_file, toml_load_from_string(updates_toml))

    if requires_root:
        # Dump the TOML contents to a temporary file (can't sudo-write)
        tmp_conf = "/tmp/{}".format(basename(toml_path))
        with open(tmp_conf, "w") as fh:
            toml_dump(conf_file, fh)

        # sudo-copy the TOML file in place
        run("sudo mv {} {}".format(tmp_conf, toml_path), shell=True, check=True)
    else:
        with open(toml_path, "w") as fh:
            toml_dump(conf_file, fh)


def split_dot_preserve_quotes(input_string):
    """
    Helper method to split a TOML key by levels (i.e. dots) when some of the
    keys may container literal strings, between quotes, with dots in them.
    For example, the following is a valid TOML key:
    'plugins."io.containerd.grpc.v1.cri".registry'
    with only three levels.
    """
    pattern = r'"([^"]+)"|([^\.]+)'
    matches = findall(pattern, input_string)

    segments = []
    for quoted, unquoted in matches:
        if quoted:
            segments.append(quoted)
        elif unquoted:
            segments.append(unquoted)

    return segments


def join_dot_preserve_quote(toml_levels):
    toml_path = [f'"{level}"' if "." in level else level for level in toml_levels]
    return ".".join(toml_path)


def read_value_from_toml(toml_file_path, toml_path, tolerate_missing=False):
    """
    Return the value in a TOML specified by a "." delimited TOML path
    """
    # Check if the pointed-to file is sudo-owned
    try:
        stat_info = stat(toml_file_path)
    except FileNotFoundError:
        if tolerate_missing:
            return ""
        print(f"ERROR: cannot find TOML at path: {toml_file_path}")
        raise RuntimeError("Error reading value from toml")

    if stat_info.st_uid == 0:
        new_toml_file_path = join("/tmp", basename(toml_file_path))
        run(f"sudo cp {toml_file_path} {new_toml_file_path}", shell=True, check=True)
        run(
            "sudo chown {}:{} {}".format(getuid(), getgid(), new_toml_file_path),
            shell=True,
            check=True,
        )

        toml_file_path = new_toml_file_path

    toml_file = toml_load(toml_file_path)
    for toml_level in split_dot_preserve_quotes(toml_path):
        if toml_level not in toml_file:
            if tolerate_missing:
                return ""

            raise RuntimeError(
                f"{toml_level} is not an entry in TOML file {toml_file_path}"
            )
        toml_file = toml_file[toml_level]

    if isinstance(toml_file, dict):
        print("ERROR: error reading from TOML, must provide a full path")
        raise RuntimeError("Haven't reached TOML leaf!")

    return toml_file


def do_remove_entry_from_toml(toml_dict, toml_path):
    toml_levels = split_dot_preserve_quotes(toml_path)
    dict_key = toml_levels[0]

    if dict_key not in toml_dict:
        return toml_dict

    if not isinstance(toml_dict[dict_key], dict):
        del toml_dict[dict_key]
        return toml_dict

    toml_dict[dict_key] = do_remove_entry_from_toml(
        toml_dict[dict_key],
        join_dot_preserve_quote(toml_levels[1:]),
    )

    return toml_dict


def remove_entry_from_toml(toml_file_path, toml_path):
    """
    Remove an entry (and all its descendants) from a TOML specified by a path.
    This method returns silently if the specified path does not exist.
    """
    toml_file = toml_load(toml_file_path)

    toml_file = do_remove_entry_from_toml(toml_file, toml_path)

    # Dump to temporary file and sudo-copy
    tmp_toml_file_path = join("/tmp", basename(toml_file_path))
    with open(tmp_toml_file_path, "w") as fh:
        toml_dump(toml_file, fh)

    run(f"sudo cp {tmp_toml_file_path} {toml_file_path}", shell=True, check=True)
    remove(tmp_toml_file_path)
