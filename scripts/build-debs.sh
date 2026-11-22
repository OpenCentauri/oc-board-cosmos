#!/bin/sh
set -eu
cosmos_sha=${1:?cosmos sha required}
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT

git clone --depth 1 https://github.com/OpenCentauri/cosmos.git "$workdir/cosmos"
git -C "$workdir/cosmos" fetch --depth 1 origin "$cosmos_sha"
git -C "$workdir/cosmos" checkout --detach "$cosmos_sha"

mkdir -p "$root/out"
# Native arm64 runner. The image itself is multi-arch; do not request QEMU.
docker run --rm \
  -v "$root:/src" \
  -v "$workdir/cosmos:/cosmos:ro" \
  -e COSMOS_SHA="$cosmos_sha" \
  -w /src \
  ghcr.io/armbian/docker-armbian-build:armbian-debian-trixie-latest \
  bash -euo pipefail /src/scripts/build-inside.sh
