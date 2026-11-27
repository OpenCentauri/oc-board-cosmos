#!/usr/bin/env python3
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out'


def deb(name):
    matches = list(OUT.glob(f'{name}_*.deb'))
    assert len(matches) == 1, f'{name}: expected one deb, got {matches}'
    return matches[0]


def contents(package):
    return subprocess.check_output(['dpkg-deb', '--contents', str(deb(package))], text=True)


def extract(package, destination):
    subprocess.check_call(['dpkg-deb', '-x', str(deb(package)), str(destination)])


for package in ('klipper', 'moonraker', 'cosmos-config', 'addon', 'cosmos-mcu-flash'):
    listing = contents(package)
    assert '/etc/init.d/' not in listing, f'{package}: stale init script'

klipper = contents('klipper')
assert '/etc/klipper/config/printer.cfg' not in klipper
assert '/etc/klipper/config/klipper-readonly/' not in klipper
assert '/lib/systemd/system/klipper.service' in klipper
assert 'canvas_rfid.py' in klipper
assert 'canvas_filament_sensor.py' in klipper

moonraker = contents('moonraker')
assert '/lib/systemd/system/moonraker.service' in moonraker
assert '/etc/klipper/config/moonraker.conf' in moonraker
assert '/etc/klipper/config/moonraker-readonly/moonraker.conf' in moonraker
assert '/etc/klipper/moonraker.asvc' in moonraker

config = contents('cosmos-config')
assert '/etc/klipper/config/printer.cfg' not in config
assert not re.search(r'/etc/klipper/config/.+\.cfg$', config, re.M)

with tempfile.TemporaryDirectory(prefix='oc-board-deb-audit-') as tmp:
    root = Path(tmp)
    for package in ('klipper', 'moonraker', 'cosmos-config', 'addon', 'cosmos-mcu-flash'):
        extract(package, root)

    readonly = (root / 'etc/klipper/config/moonraker-readonly/moonraker.conf').read_text()
    assert 'provider: systemd_cli' in readonly
    assert 'web_client: /etc/webui' in readonly
    defaults = (root / 'usr/share/config-manager/default-machine.conf').read_text()
    assert 'web_ui = fluidd' in defaults
    addons = (root / 'usr/bin/addons').read_text()
    assert '"systemctl", "restart", f"{service}.service"' in addons
    assert 'INIT_DIR' not in addons
    config_depends = subprocess.check_output(['dpkg-deb', '-f', str(deb('cosmos-config')), 'Depends'], text=True)
    cosmos_depends = subprocess.check_output(['dpkg-deb', '-f', str(deb('cosmos')), 'Depends'], text=True)
    assert 'oc-board-config-common' in config_depends
    assert 'cosmos-klipper-config' not in config_depends
    assert 'oc-board-config-cb2' in cosmos_depends

    control = root / 'control'
    subprocess.check_call(['dpkg-deb', '-e', str(deb('cosmos-mcu-flash')), str(control)])
    postinst = (control / 'postinst').read_text()
    assert 'deb-systemd-helper' in postinst
    for forbidden in ('deb-systemd-invoke start', 'deb-systemd-invoke restart', 'deb-systemd-invoke try-restart'):
        assert forbidden not in postinst

    for board in ('bed', 'toolhead', 'canvas'):
        firmware = root / f'usr/lib/firmware/klipper-{board}.bin'
        deployer = root / f'usr/lib/firmware/katapult-deployer-{board}.bin'
        version = root / f'usr/lib/firmware/klipper-{board}.bin.ver'
        unit = root / f'usr/lib/systemd/system/klipper-firmware-{board}.service'
        script = root / f'usr/libexec/cosmos-mcu-flash/klipper-firmware-{board}'
        assert firmware.stat().st_size > 0
        assert deployer.stat().st_size > 0
        assert re.fullmatch(r'[0-9a-f]{40}-r20\n', version.read_text())
        assert unit.is_file()
        unit_text = unit.read_text()
        assert 'ConditionPathExists=' not in unit_text
        assert 'OnSuccess=klipper.service' in unit_text
        assert 'OnFailure=klipper.service' in unit_text
        assert script.stat().st_mode & 0o111
        script_text = script.read_text()
        for forbidden in ('gpioset', 'gpioget', 'psplash-write', 'platform-4101400', 'platform-4200000'):
            assert forbidden not in script_text

print('DEB service/config/firmware payload audit: OK')
