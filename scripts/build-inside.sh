#!/bin/bash
set -euo pipefail

python3 "$(dirname "$0")/fetch-cosmos-pins.py" \
  kalico moonraker grumpyscreen fluidd mainsail ustreamer afc tmc-autotune katapult \
  /cosmos/meta-opencentauri
python3 "$(dirname "$0")/fetch-mcu-flasher.py" /cosmos/meta-opencentauri
python3 "$(dirname "$0")/fetch-flashtool.py" /cosmos/meta-opencentauri
python3 "$(dirname "$0")/fetch-python-deps.py"
cp /tmp/custom-python-deps/*.deb /src/out/

channel=${APT_CHANNEL:-nightly}
number=${PACKAGE_BUILD_NUMBER:-0}
case "$channel" in nightly|release) ;; *) exit 1 ;; esac
version_suffix="+${channel}.${number}.git${COSMOS_SHA:0:12}~trixie1"
shopt -s nullglob

package_version() {
  awk -v name="$1" '$1 == name { print $2 }' /tmp/package-versions
}

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

for name in fluidd mainsail moonraker klipper grumpyscreen ustreamer afc tmc-autotune mcu-flasher flashtool addon cosmos-config cosmos-mcu-flash oc-board-config cosmos; do
  build_pkg "$name"
done

OC_BOARD_DEB_DIR=/src/out python3 -m unittest tests.test_oc_board_built -v
