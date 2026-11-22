#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  build-essential debhelper devscripts git ca-certificates \
  python3 python3-setuptools \
  pkg-config curl unzip patch \
  libstdc++-14-dev

parse_pin() {
  python3 - "$1" <<'PY'
import re, sys
text = open(sys.argv[1]).read().replace("\\\n", "")
uri = re.search(r'git://([^;\s"]+)', text)
rev = re.search(r'SRCREV\s*=\s*"([0-9a-fA-F]+)"', text)
if not uri or not rev:
    sys.exit(f"missing git pin in {sys.argv[1]}")
print(f"https://{uri.group(1)}")
print(rev.group(1))
PY
}

fetch_pinned() {
  name=$1
  recipe=$2
  shift 2
  mapfile -t pin < <(parse_pin "$recipe")
  git clone "${pin[0]}" "/upstream/${name}"
  git -C "/upstream/${name}" checkout --detach "${pin[1]}"
  if [ "$name" = grumpyscreen ]; then
    git -C "/upstream/${name}" submodule update --init --recursive
  fi
  for patch_file in "$@"; do
    [ -f "$patch_file" ] || continue
    patch -d "/upstream/${name}" -p1 < "$patch_file"
  done
}

install -d /upstream
fetch_pinned kalico \
  /cosmos/meta-opencentauri/recipes-apps/klipper/kalico_2026.02.00.inc \
  /cosmos/meta-opencentauri/recipes-apps/klipper/files/*.patch
fetch_pinned moonraker \
  /cosmos/meta-opencentauri/recipes-apps/moonraker/moonraker_0.11.0.bb \
  /cosmos/meta-opencentauri/recipes-apps/moonraker/files/*.patch
fetch_pinned grumpyscreen \
  /cosmos/meta-opencentauri/recipes-apps/grumpyscreen/grumpyscreen_2.0.0.bb

version_suffix="+git${COSMOS_SHA:0:12}~trixie1"
shopt -s nullglob
build_pkg() {
  name=$1
  parent=$(mktemp -d)
  src="$parent/$name"
  mkdir -p "$src"
  cp -a "/src/packages/${name}/." "$src/"
  sed -i "1s/([^)]*)/(0.0.0${version_suffix})/" "$src/debian/changelog"
  (cd "$src" && dpkg-buildpackage -us -uc -b)
  cp "$parent/"*.deb /src/out/
}

for name in fluidd mainsail moonraker klipper grumpyscreen cosmos; do
  build_pkg "$name"
done
