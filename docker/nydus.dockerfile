FROM ghcr.io/sc2-sys/base:0.12.0

# ---------------------------
# Nydus daemon set-up
# ---------------------------

# Build the daemon and other tools like nydusify
ARG CODE_DIR=/go/src/github.com/sc2-sys/nydus
RUN mkdir -p ${CODE_DIR} \
    && git clone\
        -b sc2-main \
        https://github.com/sc2-sys/nydus.git \
        ${CODE_DIR} \
    && git config --global --add safe.directory ${CODE_DIR} \
    && cd ${CODE_DIR} \
    && rustup toolchain install 1.75.0-x86_64-unknown-linux-gnu \
    && DOCKER=false GOPROXY=https://proxy.golang.org make all-release

WORKDIR ${CODE_DIR}
