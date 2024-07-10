FROM ubuntu:22.04

#RUN sed -Ei 's/^# deb-src /deb-src /' /etc/apt/sources.list \
RUN apt update \
    && apt upgrade -y \
    && apt install -y \
        git \
        make \
        cbindgen \
        curl \
        gcc \
        libcunit1 \
        libcunit1-doc \
        libcunit1-dev \
        gettext \
        python3-venv \
        ninja-build \
        bzip2 \
        libglib2.0-dev \
        rustc \
        iasl \
        build-essential \
        libglib2.0-dev \
        libfdt-dev \
        libpixman-1-dev \
        zlib1g-dev \
        libudev-dev \
        libvdeplug-dev 
#RUN apt-get build-dep qemu

RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
RUN . "$HOME/.cargo/env" \
    && git clone --branch igvm-v0.1.6 https://github.com/microsoft/igvm/ \
    && cd igvm \
    && make -f igvm_c/Makefile \
    && make -f igvm_c/Makefile install 
RUN git clone https://github.com/coconut-svsm/qemu \
    && cd qemu \
    && git checkout svsm-igvm \
    && export PKG_CONFIG_PATH=$PKG_CONFIG_PATH:/usr/lib64/pkgconfig/ \
    && ./configure --prefix=$HOME/bin/qemu-svsm/ --target-list=x86_64-softmmu --enable-igvm \
    && ninja -C build/ \
    && make install

# /root/bin/qemu-svsm/