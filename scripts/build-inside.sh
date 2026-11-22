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
import glob, os, re, sys
name, root = sys.argv[1], sys.argv[2]

def version_key(path):
    stem = os.path.basename(path).rsplit(".", 1)[0]
    version = stem.split("_", 1)[1] if "_" in stem else "0"
    return [int(part) if part.isdigit() else part for part in re.split(r"([0-9]+)", version)]

def candidates(suffix):
    found = glob.glob(os.path.join(root, "recipes-apps", "*", f"{name}_{suffix}"))
    return sorted(found, key=version_key)

bbs = candidates("*.bb")
incs = candidates("*.inc")
if not bbs and not incs:
    sys.exit(f"no {name}_* recipe under {root}")
recipe = bbs[-1] if bbs else incs[-1]
text = open(recipe).read().replace("\\\n", "")
require = re.search(r"^require\s+(\S+)", text, re.M)
if require and "SRCREV" not in text:
    inc = os.path.join(os.path.dirname(recipe), require.group(1))
    if os.path.exists(inc):
        text += "\n" + open(inc).read().replace("\\\n", "")
        recipe = inc
uri = re.search(r"(?:git|gitsm)://([^;\s\"]+)", text)
rev = re.search(r'SRCREV\s*=\s*"([0-9a-fA-F]+)"', text)
if not uri or not rev:
    sys.exit(f"missing git pin in {recipe}")
files_dir = os.path.join(os.path.dirname(recipe), "files")
print(f"https://{uri.group(1)}")
print(rev.group(1))
print(files_dir)
PY
}

fetch_pinned() {
  name=$1
  mapfile -t pin < <(parse_pin "$name" /cosmos/meta-opencentauri)
  echo "pin ${name}: ${pin[0]} @ ${pin[1]}"
  git clone "${pin[0]}" "/upstream/${name}"
  git -C "/upstream/${name}" checkout --detach "${pin[1]}"
  if [ "$name" = grumpyscreen ]; then
    git -C "/upstream/${name}" submodule update --init --recursive
  fi
  shopt -s nullglob
  for patch_file in "${pin[2]}"/*.patch; do
    patch -d "/upstream/${name}" -p1 < "$patch_file"
  done
  shopt -u nullglob
}

install -d /upstream
fetch_pinned kalico
fetch_pinned moonraker
fetch_pinned grumpyscreen

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
