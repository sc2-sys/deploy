FROM ghcr.io/sc2-sys/base:0.12.0

# ---------------------------
# Guest Components source set-up
# ---------------------------

# Install APT dependencies
RUN apt install -y \
        musl-tools \
        pkg-config \
        protobuf-compiler \
        tss2

# Fetch code and build the runtime and the agent

WORKDIR ${CODE_DIR}
