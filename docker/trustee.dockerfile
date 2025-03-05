FROM ghcr.io/sc2-sys/base:0.12.0

# ---------------------------
# Common APT dependencies
# ---------------------------

RUN curl -fsSL https://download.01.org/intel-sgx/sgx_repo/ubuntu/intel-sgx-deb.key | \
        gpg --dearmor | tee /usr/share/keyrings/intel-sgx-archive-keyring.gpg > /dev/null \
    # TODO: update to noble
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/intel-sgx-archive-keyring.gpg] \
        https://download.01.org/intel-sgx/sgx_repo/ubuntu noble main" | \
        tee /etc/apt/sources.list.d/intel-sgx.list \
    && apt update

RUN apt install -y \
        libsgx-dcap-quote-verify-dev \
        libsgx-dcap-quote-verify \
        libtdx-attest-dev \
        libtdx-attest \
        libtss2-dev \
        openssl \
        pkg-config \
        protobuf-compiler

# ---------------------------
# Trustee source set-up
# ---------------------------

ARG CODE_DIR=/git/sc2-sys/trustee
RUN mkdir -p ${CODE_DIR} \
    && git clone\
        -b sc2-main \
        https://github.com/sc2-sys/trustee.git \
        ${CODE_DIR} \
    && git config --global --add safe.directory ${CODE_DIR}

# ---------------------------
# Build KBS
# ---------------------------

RUN cd ${CODE_DIR}/kbs \
    && openssl genpkey -algorithm ed25519 > config/private.key \
    && openssl pkey -in config/private.key -pubout -out config/public.pub \
    && make AS_FEATURE=coco-as-grpc

# ---------------------------
# Build AS
# ---------------------------

RUN cd ${CODE_DIR}/attestation-service \
    && make VERIFIER=all-verifier

# ---------------------------
# Build RVPS
# ---------------------------

RUN cd ${CODE_DIR}/rvps \
    && make build

# ---------------------------
# Build KBC
# ---------------------------

RUN cd ${CODE_DIR}/tools/kbc-client \
    && cargo build --release

WORKDIR ${CODE_DIR}
