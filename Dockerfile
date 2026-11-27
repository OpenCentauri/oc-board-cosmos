FROM ghcr.io/armbian/docker-armbian-build:armbian-debian-trixie-latest

ARG BASE_DIGEST=unknown
LABEL org.opencontainers.image.base.digest="${BASE_DIGEST}"
LABEL org.opencontainers.image.source="https://github.com/OpenCentauri/oc-board-cosmos"

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      apt-utils \
      build-essential \
      gcc-arm-none-eabi \
      libnewlib-arm-none-eabi \
      binutils-arm-none-eabi \
      debhelper \
      devscripts \
      dh-exec \
      libbsd-dev \
      libevent-dev \
      libjpeg-dev \
      libsystemd-dev \
      cargo \
      rustc \
      libudev-dev \
      quilt \
      git \
      ca-certificates \
      ccache \
      sccache \
      python3 \
      python3-all \
      python3-dev \
      python3-wheel \
      python3-serial \
      python3-jinja2 \
      python3-setuptools \
      cython3 \
      dh-python \
      pkg-config \
      curl \
      unzip \
      patch \
      sudo \
      ucf \
      libstdc++-14-dev \
 && ln -sf ../../bin/ccache /usr/lib/ccache/arm-none-eabi-gcc \
 && rm -rf /var/lib/apt/lists/*

ENV PATH="/usr/lib/ccache:${PATH}" \
    RUSTC_WRAPPER="sccache"
