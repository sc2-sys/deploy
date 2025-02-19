from os import environ


def on_azure():
    if "SC2_ON_AZURE" not in environ:
        return False

    return environ["SC2_ON_AZURE"] == "yes"
