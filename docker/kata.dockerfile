FROM ghcr.io/sc2-sys/base:0.12.0

# ---------------------------
# Kata Containers source set-up
# ---------------------------

# Install APT dependencies
RUN apt install -y \
        libseccomp-dev \
        musl-tools \
        pkg-config \
        protobuf-compiler \
        tss2

# ------------------------------------------------------------------------------
# Build Kata
#
# We need a few patches to get Knative and our baseline experiments to work
# on top of upstream Kata, so we maintain two separate source trees in our
# build container: one for the baselines (branch sc2-baseline) and one for
# SC2 (branch sc2-main). This introduces a bit of duplication but, at the same
# time, allows us to have clearly differentiated targets to, e.g., build
# different initrds.
# ------------------------------------------------------------------------------

# We must pin Kata to the rust version in kata-containers/versions.yml
ARG RUST_VERSION

# To build the Kata Agent from source we need to statically link libseccomp
# https://github.com/kata-containers/kata-containers/issues/5044
ARG LIBSECCOMP_VERSION="2.5.5"
ARG LIBSECCOMP_URL="https://github.com/seccomp/libseccomp"
ARG LIBSECCOMP_PATH="/usr/local/kata-libseccomp"
ARG GPERF_VERSION="3.1"
ARG GPERF_URL="http://ftp.gnu.org/pub/gnu/gperf/"
ARG GPERF_PATH="/usr/local/kata-gperf"

# After building libseccomp, we need to set these two env. variables to make
# sure successive builds succeed
ARG LIBSECCOMP_LINK_TYPE=static
ARG LIBSECCOMP_LIB_PATH=${LIBSECCOMP_PATH}/lib
ENV LIBSECCOMP_LINK_TYPE=${LIBSECCOMP_LINK_TYPE}
ENV LIBSECCOMP_LIB_PATH=${LIBSECCOMP_LIB_PATH}

# Fetch code and build the runtime and the agent for our baselines
ARG CODE_DIR=/go/src/github.com/kata-containers/kata-containers-baseline
RUN mkdir -p ${CODE_DIR} \
    && git clone\
        -b sc2-baseline \
        https://github.com/sc2-sys/kata-containers \
        ${CODE_DIR} \
    && git config --global --add safe.directory ${CODE_DIR} \
    && cd ${CODE_DIR}/src/runtime \
    && make \
    && cd ${CODE_DIR} \
    && ./ci/install_libseccomp.sh ${LIBSECCOMP_PATH} ${GPERF_PATH} \
    && cd ${CODE_DIR}/src/agent \
    && rustup default ${RUST_VERSION} \
    && rustup component add rust-analyzer \
    && rustup target add x86_64-unknown-linux-musl \
    && make

# Fetch code and build the runtime and the agent for SC2
ARG CODE_DIR=/go/src/github.com/kata-containers/kata-containers-sc2
RUN mkdir -p ${CODE_DIR} \
    && git clone\
        -b sc2-main \
        https://github.com/sc2-sys/kata-containers \
        ${CODE_DIR} \
    && git config --global --add safe.directory ${CODE_DIR} \
    && cd ${CODE_DIR}/src/runtime \
    && make \
    && cd ${CODE_DIR}/src/agent \
    && rustup component add rust-analyzer \
    && rustup target add x86_64-unknown-linux-musl \
    && make

# ------------------------------------------------------------------------------
# Build Guest Components
#
# The agent is very tightly-coupled with guest-components, so it makes sense
# to modify both in the same work-on container
# ------------------------------------------------------------------------------

ARG CODE_DIR_GC=/git/sc2-sys/guest-components
ARG RUST_VERSION_GC=1.81
RUN mkdir -p ${CODE_DIR_GC} \
    && git clone\
        -b sc2-main \
        https://github.com/sc2-sys/guest-components \
        ${CODE_DIR_GC} \
    && git config --global --add safe.directory ${CODE_DIR_GC} \
    && cd ${CODE_DIR_GC}/image-rs \
    && rustup override set ${RUST_VERSION_GC} \
    && cargo build --release --features "nydus"

WORKDIR ${CODE_DIR}
