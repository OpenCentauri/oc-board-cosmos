#!/bin/sh
set -eu
cosmos_sha=${1:?cosmos sha required}
root=$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)
image=${BUILDER_IMAGE:-ghcr.io/opencentauri/oc-board-cosmos:builder}
APT_CHANNEL=${APT_CHANNEL:-nightly}
OFFLINE=${OFFLINE:-0}
DOCKER_PULL=${DOCKER_PULL:-1}
case "$APT_CHANNEL" in nightly|release) ;; *) exit 1 ;; esac
case "$OFFLINE" in 0|1) ;; *) echo 'OFFLINE must be 0 or 1' >&2; exit 1 ;; esac
case "$DOCKER_PULL" in 0|1) ;; *) echo 'DOCKER_PULL must be 0 or 1' >&2; exit 1 ;; esac
cache_root=${CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/oc-board-cosmos}
workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT
mkdir -p "$cache_root/upstream" "$cache_root/downloads" "$cache_root/cargo" \
  "$cache_root/ccache" "$cache_root/sccache" "$root/out"

if [ -n "${COSMOS_DIR:-}" ]; then
  git -C "$COSMOS_DIR" cat-file -e "${cosmos_sha}^{commit}"
  mkdir "$workdir/cosmos"
  git -C "$COSMOS_DIR" archive "$cosmos_sha" | tar -x -C "$workdir/cosmos"
  cosmos=$workdir/cosmos
else
  cosmos=$cache_root/cosmos
  if [ ! -d "$cosmos/.git" ]; then
    if [ "$OFFLINE" = 1 ]; then
      echo "offline Cosmos checkout missing: $cosmos" >&2
      exit 1
    fi
    git clone --depth 1 https://github.com/OpenCentauri/cosmos.git "$cosmos"
  fi
  if ! git -C "$cosmos" cat-file -e "${cosmos_sha}^{commit}" 2>/dev/null; then
    if [ "$OFFLINE" = 1 ]; then
      echo "offline Cosmos revision missing: $cosmos_sha" >&2
      exit 1
    fi
    git -C "$cosmos" fetch --depth 1 origin "$cosmos_sha"
  fi
  git -C "$cosmos" checkout --force --detach "$cosmos_sha"
  git -C "$cosmos" reset --hard "$cosmos_sha"
  git -C "$cosmos" clean -fdx
fi

find "$root/out" -maxdepth 1 -type f -name '*.deb' -delete
if [ "$OFFLINE" = 0 ]; then
  if [ "$DOCKER_PULL" = 1 ]; then
    docker pull "$image"
  fi
  network=bridge
  cargo_offline=false
else
  network=none
  cargo_offline=true
fi

docker run --rm --pull never --network "$network" \
  -v "$root:/src" \
  -v "$cosmos:/cosmos:ro" \
  -v "$cache_root/upstream:/upstream" \
  -v "$cache_root:/cache" \
  -e COSMOS_SHA="$cosmos_sha" \
  -e PACKAGING_FINGERPRINT="${PACKAGING_FINGERPRINT:-}" \
  -e APT_CHANNEL="$APT_CHANNEL" \
  -e PACKAGE_BUILD_NUMBER="${PACKAGE_BUILD_NUMBER:-0}" \
  -e OFFLINE="$OFFLINE" \
  -e DOWNLOAD_CACHE=/cache/downloads \
  -e CARGO_HOME=/cache/cargo \
  -e CARGO_NET_OFFLINE="$cargo_offline" \
  -e CCACHE_DIR=/cache/ccache \
  -e CCACHE_MAXSIZE="${CCACHE_MAXSIZE:-1G}" \
  -e CCACHE_COMPILERCHECK=content \
  -e CCACHE_NOHASHDIR=1 \
  -e CCACHE_BASEDIR=/tmp \
  -e SCCACHE_DIR=/cache/sccache \
  -e SCCACHE_CACHE_SIZE="${SCCACHE_CACHE_SIZE:-1G}" \
  -e RUSTC_WRAPPER=sccache \
  -e GIT_TERMINAL_PROMPT=0 \
  -w /src "$image" \
  bash -euo pipefail /src/scripts/build-inside.sh

docker run --rm --pull never --network none \
  -v "$root:/src" \
  -e APT_CHANNEL="$APT_CHANNEL" \
  -e COSMOS_RELEASE_ID="${COSMOS_RELEASE_ID:-}" \
  -e COSMOS_RELEASE_TAG="${COSMOS_RELEASE_TAG:-}" \
  -e PACKAGING_FINGERPRINT="${PACKAGING_FINGERPRINT:-}" \
  -w /src "$image" \
  sh /src/scripts/stage-apt.sh "$cosmos_sha"
