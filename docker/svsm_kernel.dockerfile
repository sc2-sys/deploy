FROM ghcr.io/sc2-sys/base:0.10.0

RUN apt update \
    && apt upgrade -y \
    && apt install -y \
        bc \
        bison \
        cpio \
        flex \
        kmod \
        libelf-dev \
        libssl-dev \
        xz-utils \
        zstd

# Clone kernel source tree
ARG CODE_DIR=/git/coconut-svsm/linux
RUN mkdir -p ${CODE_DIR} \
    && git clone \
        --branch svsm \
        --depth=1 https://github.com/coconut-svsm/linux \
        ${CODE_DIR}

# Copy generated config file. The filename and path are hardcoded in ./tasks/svsm.py
COPY ./svsm_kernel_config ${CODE_DIR}/.config

ARG MODULES_OUTDIR
RUN cd ${CODE_DIR} \
    && make olddefconfig \
    && make -j $(nproc) \
    && make modules_install INSTALL_MOD_PATH=${MODULES_OUTDIR}
