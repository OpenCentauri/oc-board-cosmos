from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


class ServicePackagingTests(unittest.TestCase):
    def test_klipper_service(self):
        unit = read('packages/klipper/debian/klipper.service')
        rules = read('packages/klipper/debian/rules')
        self.assertIn('Type=simple', unit)
        self.assertIn('-X lazy_imports=all -X no_debug_ranges', unit)
        self.assertIn('/etc/klipper/config/printer.cfg', unit)
        self.assertIn('-l /board-resource/klippy.log -a /run/klippy.sock', unit)
        self.assertIn('Environment=TMPDIR=/user-resource/.tmp', unit)
        self.assertIn('cosmos-klipper-prestart', unit)
        self.assertIn('canvas_rfid.py', rules)
        self.assertIn('canvas_filament_sensor.py', rules)
        self.assertNotIn('/etc/init.d', rules)
        self.assertNotIn('klipper-readonly', rules)
        self.assertNotIn('config/printer.cfg', rules)

    def test_moonraker_service(self):
        unit = read('packages/moonraker/debian/moonraker.service')
        rules = read('packages/moonraker/debian/rules')
        control = read('packages/moonraker/debian/control')
        self.assertIn('Type=simple', unit)
        self.assertIn('Environment=PYTHONPATH=/usr/share/moonraker', unit)
        self.assertIn('-m moonraker.moonraker -d /etc/klipper', unit)
        self.assertIn('-l /board-resource/moonraker.log -u /run/moonraker.sock', unit)
        self.assertIn('cosmos-moonraker-prestart', unit)
        self.assertIn('s/provider: sysvinit/provider: systemd_cli/', rules)
        self.assertIn('web_client: /etc/webui', rules)
        self.assertIn('addon', control)
        self.assertIn('fluidd', control)
        self.assertNotIn('/etc/init.d', rules)

    def test_config_and_addon_packages(self):
        rules = read('packages/cosmos-config/debian/rules')
        helper = read('packages/cosmos-config/debian/cosmos-moonraker-prestart')
        addon = read('packages/addon/debian/rules')
        self.assertIn('centauri-carbon-1/default-machine.conf', rules)
        self.assertIn('s/^web_ui = .*/web_ui = fluidd/', rules)
        self.assertIn('build-klipper-var-config', rules)
        self.assertNotIn('printer.cfg', rules)
        self.assertNotIn('extras-readonly/', rules)
        self.assertIn('config-manager ui web_ui', helper)
        self.assertIn('addons init', helper)
        self.assertIn('ln -s /user-resource/gcodes /etc/klipper/gcodes', helper)
        klipper_helper = read('packages/cosmos-config/debian/cosmos-klipper-prestart')
        self.assertIn('mkdir -p /etc/klipper/config/moonraker-readonly', klipper_helper)
        self.assertIn('ln -s /user-resource/gcodes /etc/klipper/gcodes', klipper_helper)
        self.assertNotIn('mkdir -p /etc/klipper/gcodes', klipper_helper)
        self.assertIn('systemctl', addon)
        self.assertIn('/usr/bin/addons', addon)

    def test_new_packages_are_integrated_into_build(self):
        build = read('scripts/build-inside.sh')
        fetch = read('scripts/fetch-cosmos-pins.py')
        dockerfile = read('Dockerfile')
        cosmos = read('packages/cosmos/debian/control')
        self.assertIn('katapult', build)
        self.assertIn('cosmos-mcu-flash oc-board-config cosmos', build)
        self.assertIn('"cosmos-mcu-flash":', fetch)
        self.assertIn('gcc-arm-none-eabi', dockerfile)
        self.assertIn('libnewlib-arm-none-eabi', dockerfile)
        self.assertIn('binutils-arm-none-eabi', dockerfile)
        self.assertIn('cosmos-mcu-flash', cosmos)
        self.assertIn('oc-board-config-cb2', cosmos)
        config_control = read('packages/cosmos-config/debian/control')
        self.assertIn('oc-board-config-common', config_control)
        self.assertNotIn('cosmos-klipper-config', config_control)

    def test_firmware_is_oc_board_and_gated(self):
        rules = read('packages/cosmos-mcu-flash/debian/rules')
        self.assertIn('files/centauri-carbon-1/config.', rules)
        self.assertNotIn('centauri-carbon-2', rules)
        self.assertIn('usr/lib/systemd/system', read('packages/cosmos-mcu-flash/debian/install'))
        self.assertIn('dh_installsystemd --no-start --no-restart-after-upgrade --no-stop-on-upgrade', rules)
        self.assertEqual(rules.count('olddefconfig'), 2)
        self.assertNotIn('"build-kalico-$$board" defconfig', rules)
        self.assertNotIn('"build-katapult-$$board" defconfig', rules)
        for board in ('bed', 'toolhead', 'canvas'):
            unit = read(f'packages/cosmos-mcu-flash/debian/units/klipper-firmware-{board}.service')
            script = read(f'packages/cosmos-mcu-flash/debian/scripts/klipper-firmware-{board}')
            self.assertIn('Type=oneshot', unit)
            self.assertNotIn('ConditionPathExists=', unit)
            self.assertIn('Conflicts=klipper.service', unit)
            self.assertIn('OnFailure=klipper.service', unit)
            self.assertIn('if [ ! -f /etc/mcu-flash-enable ]', script)
            self.assertIn('if [ ! -e "$SERIALPORT" ]', script)
            self.assertIn('cp "$FIRMWARE_VERSION" "$INSTALLED_VERSION" || exit 1', script)
            self.assertIn('New plan needed for booting into Katapult', script)
            self.assertNotIn('gpioset', script)
            self.assertNotIn('gpioget', script)
            self.assertNotIn('psplash-write', script)
            self.assertNotIn('platform-4101400', script)
            self.assertNotIn('platform-4200000', script)
        canvas = read('packages/cosmos-mcu-flash/debian/scripts/klipper-firmware-canvas')
        self.assertIn('config-manager extras elegoo_canvas True || exit 1', canvas)


if __name__ == '__main__':
    unittest.main()
