#!/bin/sh
set -eu
cosmos_sha=${1:?cosmos sha required}
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
image=${BUILDER_IMAGE:-ghcr.io/opencentauri/oc-board-cosmos:builder}
APT_CHANNEL=${APT_CHANNEL:-nightly}
case "$APT_CHANNEL" in nightly|release) ;; *) exit 1 ;; esac
workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT

git clone --depth 1 https://github.com/OpenCentauri/cosmos.git "$workdir/cosmos"
git -C "$workdir/cosmos" fetch --depth 1 origin "$cosmos_sha"
git -C "$workdir/cosmos" checkout --detach "$cosmos_sha"

mkdir -p "$root/out"
find "$root/out" -maxdepth 1 -type f -name '*.deb' -delete
docker pull "$image"
docker run --rm \
  -v "$root:/src" \
  -v "$workdir/cosmos:/cosmos:ro" \
  -e COSMOS_SHA="$cosmos_sha" \
  -e APT_CHANNEL="$APT_CHANNEL" \
  -e PACKAGE_BUILD_NUMBER="${PACKAGE_BUILD_NUMBER:-0}" \
  -w /src "$image" \
  bash -euo pipefail /src/scripts/build-inside.sh

docker run --rm \
  -v "$root:/src" \
  -e APT_CHANNEL="$APT_CHANNEL" \
  -e COSMOS_RELEASE_ID="${COSMOS_RELEASE_ID:-}" \
  -e COSMOS_RELEASE_TAG="${COSMOS_RELEASE_TAG:-}" \
  -w /src "$image" \
  sh /src/scripts/stage-apt.sh "$cosmos_sha"
