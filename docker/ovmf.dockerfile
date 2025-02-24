FROM ghcr.io/sc2-sys/base:0.10.0

RUN apt update \
    && apt upgrade -y \
    && apt install -y \
        dosfstools \
        grub2-common \
        grub-efi \
        iasl \
        mtools \
        nasm \
        uuid-dev

ARG OVMF_VERSION
ARG CODE_DIR=/git/sc2-sys/edk2
RUN mkdir -p ${CODE_DIR} \
    && git clone \
        --branch ${OVMF_VERSION} \
        --depth 1 \
        https://github.com/tianocore/edk2.git \
        ${CODE_DIR} \
    && cd ${CODE_DIR} \
    && git submodule update --init \
    && export PYTHON3_ENABLE=TRUE \
    && export PYTHON_COMMAND=python3 \
    && make -j $(nproc) -C BaseTools/ \
    && . ./edksetup.sh --reconfig \
    && build -a X64 -b RELEASE -t GCC5 -p OvmfPkg/OvmfPkgX64.dsc \
    && touch  OvmfPkg/AmdSev/Grub/grub.efi \
    && build -a X64 -b RELEASE -t GCC5 -p OvmfPkg/AmdSev/AmdSevX64.dsc
