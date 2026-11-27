FROM ghcr.io/armbian/docker-armbian-build:armbian-debian-trixie-latest

ARG BASE_DIGEST=unknown
LABEL org.opencontainers.image.base.digest="${BASE_DIGEST}"
LABEL org.opencontainers.image.source="https://github.com/OpenCentauri/oc-board-cosmos"

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      apt-utils \
      build-essential \
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
 && rm -rf /var/lib/apt/lists/*
