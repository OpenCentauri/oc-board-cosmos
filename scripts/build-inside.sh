#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  build-essential debhelper devscripts git ca-certificates \
  python3 python3-setuptools \
  pkg-config curl unzip \
  libstdc++-14-dev

version_suffix="+git${COSMOS_SHA:0:12}~trixie1"
shopt -s nullglob
build_pkg() {
  name=$1
  parent=$(mktemp -d)
  src="$parent/$name"
  mkdir -p "$src"
  cp -a "/src/packages/${name}/." "$src/"
  prepare_$name "$src"
  sed -i "1s/([^)]*)/(0.0.0${version_suffix})/" "$src/debian/changelog"
  (cd "$src" && dpkg-buildpackage -us -uc -b)
  cp "$parent/"*.deb /src/out/
}

prepare_cosmos() { :; }
prepare_fluidd() { :; }
prepare_mainsail() { :; }
prepare_moonraker() {
  src=$1
  mkdir -p "$src/debian/patches"
  cp -a /cosmos/meta-opencentauri/recipes-apps/moonraker/files/*.patch "$src/debian/patches/" || true
  ls "$src/debian/patches/"*.patch 2>/dev/null | xargs -n1 basename > "$src/debian/patches/series" || true
}
prepare_klipper() { :; }
prepare_grumpyscreen() { :; }

for name in fluidd mainsail moonraker klipper grumpyscreen cosmos; do
  build_pkg "$name"
done
