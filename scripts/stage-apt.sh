#!/bin/sh
set -eu
sha=${1:?cosmos sha required}
channel=${APT_CHANNEL:-nightly}
case "$channel" in nightly|release) ;; *) exit 1 ;; esac
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
dest="$root/publish/$channel/trixie/arm64"
mkdir -p "$dest"
cp "$root/out/"*.deb "$dest/"
cd "$dest"
apt-ftparchive packages . > Packages
gzip -c Packages > Packages.gz
apt-ftparchive release . > Release
printf '%s\n' "$sha" > cosmos-sha
python3 - "$sha" "$channel" <<'PY'
import json
import os
import sys
with open('build.json', 'w') as handle:
    json.dump(dict(sha=sys.argv[1], channel=sys.argv[2], release_id=os.environ.get('COSMOS_RELEASE_ID', ''), tag=os.environ.get('COSMOS_RELEASE_TAG', '')), handle)
    handle.write('\n')
PY
