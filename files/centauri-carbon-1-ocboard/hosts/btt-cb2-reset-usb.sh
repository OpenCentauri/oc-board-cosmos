#!/bin/sh
set -u

device=${OC_BOARD_USB_DEVICE:-xhci-hcd.0.auto}
driver=${OC_BOARD_USB_DRIVER:-/sys/bus/platform/drivers/xhci-hcd}
status=0

write_sysfs() {
    printf '%s\n' "$device" | tee "$driver/$1" >/dev/null
}

# shellcheck disable=SC2317
rebind() {
    attempt=1
    while [ "$attempt" -le 5 ]; do
        if write_sysfs bind; then
            return 0
        fi
        attempt=$((attempt + 1))
        [ "$attempt" -gt 5 ] || sleep 1
    done
    echo "Failed to rebind $device after five attempts" >&2
    return 1
}

# Shellcheck does not model trap callbacks.
# shellcheck disable=SC2317
on_exit() {
    status=$?
    trap - EXIT HUP INT TERM
    rebind || status=$?
    exit "$status"
}

trap on_exit EXIT
trap 'exit 1' HUP INT TERM

if ! write_sysfs unbind; then
    echo "Failed to unbind $device; attempting to restore it" >&2
    status=1
elif ! sleep 2; then
    status=1
fi

exit "$status"
