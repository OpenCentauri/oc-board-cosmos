#!/bin/bash
set -euo pipefail

flash_deb=$(find /src/out -maxdepth 1 -name 'cosmos-mcu-flash_*.deb' -print -quit)
test -n "$flash_deb"
dpkg -x "$flash_deb" /

calls=/tmp/mcu-flash-calls
rm -f "$calls"
cat > /usr/bin/flashtool <<'EOF'
#!/bin/sh
printf 'flashtool %s\n' "$*" >> /tmp/mcu-flash-calls
exit "${FLASH_TOOL_STATUS:-0}"
EOF
cat > /usr/bin/mcu-flasher <<'EOF'
#!/bin/sh
printf 'mcu-flasher %s\n' "$*" >> /tmp/mcu-flash-calls
exit "${MCU_FLASHER_STATUS:-0}"
EOF
cat > /usr/bin/udevadm <<'EOF'
#!/bin/sh
printf 'ID_VENDOR=%s\n' "${UDEV_VENDOR:-Other}"
EOF
chmod +x /usr/bin/flashtool /usr/bin/mcu-flasher /usr/bin/udevadm

scripts=(bed toolhead canvas)
rm -f /etc/mcu-flash-enable
test ! -e /dev/ttyS0
test ! -e /dev/serial/by-path/platform-xhci-hcd.0.auto-usb-0:1.3:1.0
test ! -e /dev/serial/by-path/platform-xhci-hcd.0.auto-usbv2-0:1.2:1.0

for board in "${scripts[@]}"; do
  "/usr/libexec/cosmos-mcu-flash/klipper-firmware-$board" start
done
test ! -e "$calls"

touch /etc/mcu-flash-enable
for board in "${scripts[@]}"; do
  "/usr/libexec/cosmos-mcu-flash/klipper-firmware-$board" start
done
test ! -e "$calls"

touch /dev/ttyS0
mkdir -p /dev/serial/by-path
touch /dev/serial/by-path/platform-xhci-hcd.0.auto-usb-0:1.3:1.0
touch /dev/serial/by-path/platform-xhci-hcd.0.auto-usbv2-0:1.2:1.0
cat > /usr/bin/config-manager <<'EOF'
#!/bin/sh
if [ "$#" -eq 2 ]; then
  printf '%s\n' True
else
  exit 1
fi
EOF
chmod +x /usr/bin/config-manager
for board in "${scripts[@]}"; do
  cp "/usr/lib/firmware/klipper-$board.bin.ver" "/etc/$board.ver"
  "/usr/libexec/cosmos-mcu-flash/klipper-firmware-$board" start
done
test ! -e "$calls"

rm -f /etc/bed.ver
/usr/libexec/cosmos-mcu-flash/klipper-firmware-bed start
cmp /usr/lib/firmware/klipper-bed.bin.ver /etc/bed.ver
grep -q 'flashtool.*-f' "$calls"
rm -f "$calls" /etc/bed.ver
mkdir -p /etc/bed.ver/klipper-bed.bin.ver
if /usr/libexec/cosmos-mcu-flash/klipper-firmware-bed start; then
  printf '%s\n' 'Version-marker failure returned success' >&2
  exit 1
fi
if grep -q mcu-flasher "$calls"; then
  printf '%s\n' 'Version-marker failure incorrectly entered Katapult fallback' >&2
  exit 1
fi
rm -rf /etc/bed.ver

rm -f "$calls" /etc/toolhead.ver
export FLASH_TOOL_STATUS=1
if /usr/libexec/cosmos-mcu-flash/klipper-firmware-toolhead start; then
  printf '%s\n' 'Failed toolhead flash returned success' >&2
  exit 1
fi
test ! -e /etc/toolhead.ver
unset FLASH_TOOL_STATUS

cat > /usr/bin/config-manager <<'EOF'
#!/bin/sh
if [ "$#" -eq 2 ]; then
  printf '%s\n' False
else
  exit 1
fi
EOF
export UDEV_VENDOR=ShenZhenCBD
rm -f "$calls" /etc/canvas.ver
if /usr/libexec/cosmos-mcu-flash/klipper-firmware-canvas start; then
  printf '%s\n' 'Failed Canvas enable returned success' >&2
  exit 1
fi
test ! -e "$calls"

printf '%s\n' 'MCU gate, device, version, failure, and Canvas checks: OK'
