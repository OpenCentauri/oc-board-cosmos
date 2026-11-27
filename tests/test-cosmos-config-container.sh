#!/bin/bash
set -euo pipefail

config_deb=$(find /src/out -maxdepth 1 -name 'cosmos-config_*.deb' -print -quit)
addon_deb=$(find /src/out -maxdepth 1 -name 'addon_*.deb' -print -quit)
test -n "$config_deb"
test -n "$addon_deb"
dpkg -x "$config_deb" /
dpkg -x "$addon_deb" /

mkdir -p /etc/klipper/config/klipper-readonly
mkdir -p /etc/klipper/config/extras-readonly
printf '[include klipper-readonly/*.cfg]\n' > /etc/klipper/config/printer.cfg
before=$(sha256sum /etc/klipper/config/printer.cfg)

/usr/bin/cosmos-klipper-prestart
test -d /etc/klipper/config/moonraker-readonly
test "$(readlink /etc/klipper/gcodes)" = /user-resource/gcodes
/usr/bin/config-manager extras elegoo_canvas True
/usr/bin/build-klipper-var-config
python3 - <<'PY'
from pathlib import Path
assert '[include ../extras-readonly/canvas.cfg]' in Path('/etc/klipper/config/klipper-readonly/zextras.cfg').read_text()
assert Path('/etc/klipper/config/moonraker-readonly/zupdate.conf').is_file()
PY

/usr/bin/config-manager extras elegoo_canvas False
/usr/bin/build-klipper-var-config
python3 - <<'PY'
from pathlib import Path
assert '[include ../extras-readonly/canvas.cfg]' not in Path('/etc/klipper/config/klipper-readonly/zextras.cfg').read_text()
PY

test "$before" = "$(sha256sum /etc/klipper/config/printer.cfg)"
printf '#*# migration-test\n' >> /etc/klipper/config/printer.cfg
rm -rf /etc/klipper/config/config-backups
rm -f /etc/klipper-config.ver
/usr/bin/cosmos-klipper-prestart
backup_count=$(find /etc/klipper/config/config-backups -name 'printer-*.cfg' | wc -l)
test "$backup_count" -eq 1
if grep -q '^#\*#' /etc/klipper/config/printer.cfg; then
  printf '%s\n' 'SAVE_CONFIG lines were not removed' >&2
  exit 1
fi
/usr/bin/cosmos-moonraker-prestart
test "$(readlink /etc/webui)" = /var/www/fluidd
/usr/bin/addons -h >/dev/null
printf '%s\n' 'Cosmos config, Canvas toggle, Fluidd selection, and addon init: OK'
