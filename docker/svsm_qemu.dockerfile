FROM ghcr.io/sc2-sys/base:0.10.0

RUN apt update \
    && apt upgrade -y \
    && apt install -y \
        bzip2 \
        cbindgen \
        gettext \
        iasl \
        libcunit1-dev \
        libfdt-dev \
        libglib2.0-dev \
        libpixman-1-dev \
        libudev-dev \
        libvdeplug-dev \
        nasm \
        ninja-build \
        python3-tomli \
        python3-venv \
        seabios \
        zlib1g-dev

# Clone and build IGVM
ARG IGVM_VERSION
ARG CODE_DIR=/git/microsoft/igvm
RUN mkdir -p ${CODE_DIR} \
    && git clone --branch igvm-v${IGVM_VERSION} https://github.com/microsoft/igvm/ ${CODE_DIR} \
    && cd ${CODE_DIR} \
    && make -f igvm_c/Makefile \
    && make -f igvm_c/Makefile install

# Clone and build SVSM's OVMF
ARG CODE_DIR=/git/coconut-svsm/edk2
RUN mkdir -p ${CODE_DIR} \
    && git clone https://github.com/coconut-svsm/edk2 ${CODE_DIR} \
    && cd ${CODE_DIR} \
    && git checkout svsm \
    && git submodule init \
    && git submodule update \
    && export PYTHON3_ENABLE=TRUE \
    && export PYTHON_COMMAND=python3 \
    && make -j $(nproc) -C BaseTools/ \
    && . ./edksetup.sh --reconfig \
    && build -a X64 -b RELEASE -t GCC5 -DTPM2_ENABLE -p OvmfPkg/OvmfPkgX64.dsc \
    && build -a X64 -b DEBUG -t GCC5 -DTPM2_ENABLE -p OvmfPkg/OvmfPkgX64.dsc

# Clone and build IGVM-enabled Qemu
ARG QEMU_DATADIR
ARG QEMU_PREFIX
ARG CODE_DIR=/git/coconut-svsm/qemu
RUN mkdir -p ${CODE_DIR} \
    && git clone https://github.com/coconut-svsm/qemu ${CODE_DIR} \
    && cd ${CODE_DIR} \
    && git checkout svsm-igvm \
    && export PKG_CONFIG_PATH=$PKG_CONFIG_PATH:/usr/lib64/pkgconfig/ \
    && ./configure \
        --cpu=x86_64 \
        # The `--datadir` flag is the path where QEMU will look for firmware
        # images. The default `--datadir` path when using a system provisioned
        # by the operator is: `/opt/confidential-containers/share/kata-qemu`.
        # For our QEMu fork we use `/opt/sc2/svsm/share/qemu
        --datadir=${QEMU_DATADIR} \
        --prefix=${QEMU_PREFIX} \
        --target-list=x86_64-softmmu \
        # Must enable IGVM
        --enable-igvm \
        --enable-kvm \
        --enable-slirp \
        --enable-trace-backends=log,simple \
        # As a reference we use Kata's --disable-x flags when building QEMU:
        # https://github.com/kata-containers/kata-containers/blob/main/tools/packaging/scripts/configure-hypervisor.sh
        --disable-auth-pam \
        --disable-brlapi \
        --disable-bsd-user \
        --disable-capstone \
        --disable-curl \
        --disable-curses \
        --disable-debug-tcg \
        --disable-docs \
        --disable-gio \
        --disable-glusterfs \
        --disable-gtk \
        --disable-guest-agent \
        --disable-guest-agent-msi \
        --disable-libiscsi \
        --disable-libudev \
        --disable-libnfs \
        --disable-libusb \
        --disable-linux-user \
        --disable-lzo \
        --disable-opengl \
        --disable-rdma \
        --disable-replication \
        --disable-sdl \
        --disable-snappy \
        --disable-spice \
        --disable-tcg-interpreter \
        --disable-tools \
        --disable-tpm \
        --disable-usb-redir \
        --disable-vde \
        --disable-vte \
        --disable-virglrenderer \
        --disable-vnc \
        --disable-vnc-jpeg \
        --disable-vnc-sasl \
        --disable-vte \
        --disable-xen \
    && make -j $(nproc) \
    && make install -j $(nproc)
