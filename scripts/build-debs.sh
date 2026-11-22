#!/bin/sh
set -eu
cosmos_sha=${1:?cosmos sha required}
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
image=${BUILDER_IMAGE:-ghcr.io/opencentauri/oc-board-cosmos:builder}
workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT

git clone --depth 1 https://github.com/OpenCentauri/cosmos.git "$workdir/cosmos"
git -C "$workdir/cosmos" fetch --depth 1 origin "$cosmos_sha"
git -C "$workdir/cosmos" checkout --detach "$cosmos_sha"

mkdir -p "$root/out"
docker pull "$image"
docker run --rm \
  -v "$root:/src" \
  -v "$workdir/cosmos:/cosmos:ro" \
  -e COSMOS_SHA="$cosmos_sha" \
  -w /src \
  "$image" \
  bash -euo pipefail /src/scripts/build-inside.sh
