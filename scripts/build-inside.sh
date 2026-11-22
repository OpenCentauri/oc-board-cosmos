#!/bin/bash
set -euo pipefail

# Read meta-opencentauri pins, fetch those sources under /upstream, and write
# /tmp/package-versions. The Python file owns the BitBake parsing.
python3 "$(dirname "$0")/fetch-cosmos-pins.py" \
  kalico moonraker grumpyscreen fluidd mainsail \
  /cosmos/meta-opencentauri

version_suffix="+git${COSMOS_SHA:0:12}~trixie1"
shopt -s nullglob

# Print the upstream version recorded for a Debian package name.
# Called as package_version klipper.
package_version() {
  awk -v name="$1" '$1 == name { print $2 }' /tmp/package-versions
}

# Build one binary package from packages/<name> and copy the .deb to /src/out.
# Called as build_pkg fluidd. COSMOS_SHA must be set.
build_pkg() {
  name=$1
  version=$(package_version "$name")
  test -n "$version"
  parent=$(mktemp -d)
  src="$parent/$name"
  mkdir -p "$src"
  cp -a "/src/packages/${name}/." "$src/"
  sed -i "1s/([^)]*)/(${version}${version_suffix})/" "$src/debian/changelog"
  (cd "$src" && dpkg-buildpackage -us -uc -b)
  cp "$parent/"*.deb /src/out/
}

for name in fluidd mainsail moonraker klipper grumpyscreen cosmos; do
  build_pkg "$name"
done
