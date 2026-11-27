import configparser
import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIGS = ROOT / "files/centauri-carbon-1-ocboard"
PACKAGE = ROOT / "packages/oc-board-config/debian"


def read_config(path):
    parser = configparser.RawConfigParser(
        strict=False, inline_comment_prefixes=(";", "#"), allow_no_value=True
    )
    parser.read_string(path.read_text())
    return parser


class OcBoardConfigTests(unittest.TestCase):
    def test_packages_are_registered_with_one_host_selected(self):
        control = (PACKAGE / "control").read_text()
        self.assertIn("Package: oc-board-config-common", control)
        self.assertIn("Package: oc-board-config-cb2", control)
        self.assertIn("Depends: ${misc:Depends}, ucf", control)
        self.assertIn("Breaks: klipper (<< ${klipper:Version})", control)
        self.assertIn("Depends: ${misc:Depends}, oc-board-config-common, afc, sudo", control)
        self.assertIn("Breaks: afc (<< ${afc:Version})", control)
        self.assertIn("Provides: oc-board-config-host", control)
        self.assertIn("Conflicts: oc-board-config-host", control)

        cosmos = (ROOT / "packages/cosmos/debian/control").read_text()
        self.assertIn("oc-board-config-cb2", cosmos)
        build = (ROOT / "scripts/build-inside.sh").read_text()
        self.assertIn(" oc-board-config ", build)
        versions = (ROOT / "scripts/fetch-cosmos-pins.py").read_text()
        self.assertIn('"oc-board-config"', versions)

    def test_config_payload_ownership_is_not_duplicated(self):
        klipper = (ROOT / "packages/klipper/debian/rules").read_text()
        self.assertNotIn("/etc/klipper/config", klipper)
        afc = (ROOT / "packages/afc/debian/rules").read_text()
        self.assertNotIn(" afc.cfg canvas.cfg ", afc)
        fingerprint = (ROOT / "scripts/select-channel.py").read_text()
        self.assertIn("root / 'files'", fingerprint)

    def test_cb2_files_own_only_host_integration(self):
        host = read_config(CONFIGS / "hosts/btt-cb2.cfg")
        self.assertEqual(
            set(host.sections()),
            {"mcu", "mcu bed", "mcu hotend", "gcode_shell_command RESET_USB",
             "gcode_macro RESET_USB"},
        )
        for section in ("mcu", "mcu bed", "mcu hotend"):
            self.assertEqual(set(host.options(section)), {"serial"})
        self.assertEqual(
            host["mcu"]["serial"],
            "/dev/serial/by-path/platform-xhci-hcd.0.auto-usb-0:1.1:1.0",
        )
        self.assertEqual(host["mcu bed"]["serial"], "/dev/ttyS0")
        self.assertEqual(
            host["mcu hotend"]["serial"],
            "/dev/serial/by-path/platform-xhci-hcd.0.auto-usb-0:1.3:1.0",
        )
        self.assertEqual(
            host["gcode_shell_command RESET_USB"]["command"],
            "sudo -n /usr/lib/klipper/reset-usb.sh",
        )
        self.assertIn(
            "RUN_SHELL_COMMAND CMD=RESET_USB",
            host["gcode_macro RESET_USB"]["gcode"],
        )

        helper = (CONFIGS / "hosts/btt-cb2-reset-usb.sh").read_text()
        self.assertIn("OC_BOARD_USB_DEVICE:-xhci-hcd.0.auto", helper)
        self.assertIn("write_sysfs unbind", helper)
        self.assertIn("write_sysfs bind", helper)
        self.assertIn("trap on_exit EXIT", helper)
        self.assertIn('while [ "$attempt" -le 5 ]', helper)
        sudoers = (CONFIGS / "hosts/btt-cb2.sudoers").read_text()
        self.assertEqual(
            sudoers,
            'ALL ALL=(root) NOPASSWD: /usr/lib/klipper/reset-usb.sh ""\n',
        )

        canvas = read_config(CONFIGS / "hosts/btt-cb2-canvas.cfg")
        self.assertEqual(
            canvas["mcu canvas"]["serial"],
            "/dev/serial/by-path/platform-xhci-hcd.0.auto-usbv2-0:1.2:1.0",
        )
        self.assertEqual(canvas["include canvas-common.cfg"], {})
        self.assertNotIn("mcu canvas", host.sections())

    def test_reset_usb_helper_failure_recovery(self):
        helper = CONFIGS / "hosts/btt-cb2-reset-usb.sh"
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            bindir = root / "bin"
            bindir.mkdir()
            driver = root / "driver"
            driver.mkdir()
            calls = root / "calls"
            count = root / "count"

            tee = bindir / "tee"
            tee.write_text("""#!/bin/sh
name=${1##*/}
printf '%s\\n' "$name" >> "$CALLS"
if [ "$name" = unbind ] && [ "${FAIL_UNBIND:-0}" = 1 ]; then exit 1; fi
if [ "$name" = bind ]; then
    attempts=0
    [ ! -f "$COUNT" ] || attempts=$(cat "$COUNT")
    attempts=$((attempts + 1))
    printf '%s\\n' "$attempts" > "$COUNT"
    if [ "${FAIL_BIND:-}" = always ]; then exit 1; fi
    if [ "${FAIL_BIND:-}" = once ] && [ "$attempts" -eq 1 ]; then exit 1; fi
fi
cat >/dev/null
""")
            sleep = bindir / "sleep"
            sleep.write_text("""#!/bin/sh
if [ "${INTERRUPT:-0}" = 1 ]; then
    kill -TERM "$PPID"
    exit 1
fi
exit 0
""")
            tee.chmod(0o755)
            sleep.chmod(0o755)

            scenarios = (
                ("normal", {}, 0, ["unbind", "bind"]),
                ("unbind_failure", {"FAIL_UNBIND": "1"}, 1, ["unbind", "bind"]),
                ("interrupted", {"INTERRUPT": "1"}, 1, ["unbind", "bind"]),
                ("bind_retry", {"FAIL_BIND": "once"}, 0,
                 ["unbind", "bind", "bind"]),
                ("bind_persistent_failure", {"FAIL_BIND": "always"}, 1,
                 ["unbind"] + ["bind"] * 5),
            )
            for name, extra, expected_status, expected_calls in scenarios:
                with self.subTest(name=name):
                    calls.write_text("")
                    count.unlink(missing_ok=True)
                    env = os.environ.copy()
                    env.update({
                        "PATH": f"{bindir}:/usr/bin:/bin",
                        "OC_BOARD_USB_DRIVER": str(driver),
                        "CALLS": str(calls),
                        "COUNT": str(count),
                        **extra,
                    })
                    result = subprocess.run(
                        ["/bin/sh", str(helper)], env=env,
                        capture_output=True, text=True, timeout=5,
                    )
                    self.assertEqual(result.returncode, expected_status,
                                     result.stderr)
                    self.assertEqual(calls.read_text().splitlines(),
                                     expected_calls)

    def test_machine_preserves_oc_board_hardware_with_cosmos_defaults(self):
        path = CONFIGS / "machine.cfg"
        text = path.read_text()
        machine = read_config(path)
        self.assertEqual(machine["stepper_x"]["step_pin"], "PB15")
        self.assertEqual(machine["stepper_y"]["step_pin"], "PD10")
        self.assertEqual(machine["heater_bed"]["heater_pin"], "PA1")
        self.assertEqual(machine["load_cell_probe"]["sensor_type"], "hx711s")
        self.assertEqual(
            machine["load_cell_probe"]["dout_pins"],
            "bed:PB14, bed:PC8, bed:PB15, bed:PA8",
        )
        self.assertEqual(machine["stepper_z"]["position_max"], "258")
        self.assertEqual(machine["tmc2209 stepper_x"]["driver_PWM_AUTOSCALE"], "true")
        self.assertIn("gcode_button extruder_board_detect", machine)
        self.assertNotIn("temperature_sensor chamber", machine)
        self.assertNotIn("pwm_cycle_time _buzzer_mainboard", machine)

        self.assertEqual(machine["heater_bed"]["min_temp"], "0")
        self.assertEqual(machine["heater_bed"]["max_temp"], "125")
        self.assertNotIn("max_power", machine["heater_bed"])
        self.assertEqual(machine["extruder"]["control"], "pid")
        self.assertEqual(machine["extruder"]["pid_Kp"], "24.860427")
        self.assertEqual(machine["bed_mesh"]["mesh_min"], "10,10")
        self.assertEqual(machine["bed_mesh"]["mesh_max"], "246,246")
        self.assertEqual(machine["bed_mesh"]["probe_count"], "9,9")
        self.assertEqual(machine["virtual_sdcard"]["path"], "/etc/klipper/gcodes")

        for section in ("mcu", "mcu bed", "mcu hotend"):
            self.assertNotIn("serial", machine[section])
        self.assertNotIn("SAVE_CONFIG", text)
        self.assertNotIn("[shaketune]", text)
        self.assertNotIn("RESET_USB", text)

    def test_rules_reproduce_cosmos_names_without_stock_machine(self):
        rules = (PACKAGE / "rules").read_text()
        self.assertIn("COSMOS_KLIPPER = /cosmos/meta-opencentauri/recipes-apps/klipper/files", rules)
        self.assertIn("dpkg-deb -f /src/out/klipper_*.deb Version", rules)
        self.assertIn("dpkg-deb -f /src/out/afc_*.deb Version", rules)
        self.assertIn("$(COSMOS_KLIPPER)/printer.cfg", rules)
        self.assertIn("/usr/share/oc-board-config/printer.cfg", rules)
        self.assertNotIn("$(COMMON)/etc/klipper/config/printer.cfg", rules)
        postinst = (PACKAGE / "oc-board-config-common.postinst").read_text()
        self.assertIn("ucf --debconf-ok", postinst)
        self.assertIn("/usr/share/oc-board-config/printer.cfg", postinst)
        self.assertIn("/etc/klipper/config/printer.cfg", postinst)
        self.assertFalse((PACKAGE / "oc-board-config-common.postrm").exists())
        self.assertIn("shared-macros.cfg", rules)
        self.assertIn("centauri-carbon-1/macros.cfg", rules)
        self.assertIn("klipper-readonly/ymacros.cfg", rules)
        self.assertIn("OC_BOARD = /src/files/centauri-carbon-1-ocboard", rules)
        self.assertIn("$(OC_BOARD)/machine.cfg", rules)
        self.assertNotIn("centauri-carbon-1/machine.cfg", rules)
        self.assertIn("klipper-readonly/zcb2.cfg", rules)
        self.assertIn("extras-readonly/canvas.cfg", rules)


if __name__ == "__main__":
    unittest.main()
