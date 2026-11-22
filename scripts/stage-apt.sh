#!/bin/sh
set -eu
sha=${1:?cosmos sha required}
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
dest="$root/publish/trixie/arm64"
mkdir -p "$dest"
cp "$root/out/"*.deb "$dest/"
cd "$dest"
apt-ftparchive packages . > Packages
gzip -c Packages > Packages.gz
apt-ftparchive release . > Release
printf '%s\n' "$sha" > cosmos-sha
