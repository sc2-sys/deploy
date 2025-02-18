FROM ghcr.io/sc2-sys/base:0.10.0

RUN apt update \
    && apt upgrade -y \
    && apt install -y \
        autoconf \
        autoconf-archive \
        libssl-dev \
        pkg-config

ARG OVMF_FILE
COPY ./${OVMF_FILE} /bin/ovmf-svsm.fd

ARG CODE_DIR=/git/coconut-svsm/svsm
RUN mkdir -p ${CODE_DIR} \
    && git clone https://github.com/coconut-svsm/svsm ${CODE_DIR} \
    && cd ${CODE_DIR} \
    && git submodule update --init \
    && rustup target add x86_64-unknown-none \
    && cargo install bindgen-cli
    # && FW_FILE=/bin/ovmf-svsm.fd make
