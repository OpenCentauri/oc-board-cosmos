import importlib
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import types
import unittest


DEB_DIR = os.environ.get("OC_BOARD_DEB_DIR")
COSMOS = pathlib.Path(os.environ.get("COSMOS_ROOT", "/cosmos/meta-opencentauri"))
KALICO = pathlib.Path(os.environ.get("KALICO_ROOT", "/upstream/kalico"))


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, **kwargs)


def package_field(package, *fields):
    return run("dpkg-deb", "-f", str(package), *fields).stdout


def payload(package):
    result = {}
    for line in run("dpkg-deb", "-c", str(package)).stdout.splitlines():
        if line.startswith("d"):
            continue
        fields = line.split(None, 5)
        result[fields[5][1:]] = fields[0]
    return result


@unittest.skipUnless(DEB_DIR, "run inside the package build")
class BuiltOcBoardConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        root = pathlib.Path(cls.tmp.name)
        assert DEB_DIR is not None
        packages = pathlib.Path(DEB_DIR)
        cls.common = cls.one(packages, "oc-board-config-common_*.deb")
        cls.cb2 = cls.one(packages, "oc-board-config-cb2_*.deb")
        cls.klipper = cls.one(packages, "klipper_*.deb")
        cls.afc = cls.one(packages, "afc_*.deb")
        cls.common_root = root / "common"
        cls.cb2_root = root / "cb2"
        cls.control = root / "control"
        for package, dest in ((cls.common, cls.common_root), (cls.cb2, cls.cb2_root)):
            dest.mkdir()
            run("dpkg-deb", "-x", str(package), str(dest))
        run("dpkg-deb", "-e", str(cls.common), str(cls.control))
        cls.config = root / "config"
        shutil.copytree(cls.common_root / "etc/klipper/config", cls.config)
        shutil.copytree(
            cls.cb2_root / "etc/klipper/config", cls.config, dirs_exist_ok=True
        )
        afc = COSMOS / "recipes-data/klipper-afc-addon/files"
        for name in ("afc.cfg", "boxturtle.cfg", "canvas_rfid.cfg"):
            shutil.copy(afc / name, cls.config / "extras-readonly" / name)

    @staticmethod
    def one(root, pattern):
        found = list(root.glob(pattern))
        if len(found) != 1:
            raise AssertionError(f"Expected one {pattern}, got {found}")
        return found[0]

    def test_real_package_payload_metadata_and_modes(self):
        common = payload(self.common)
        cb2 = payload(self.cb2)
        self.assertIn("/usr/share/oc-board-config/printer.cfg", common)
        self.assertNotIn("/etc/klipper/config/printer.cfg", common)
        self.assertIn("/etc/klipper/config/klipper-readonly/machine.cfg", common)
        self.assertIn("/etc/klipper/config/klipper-readonly/ymacros.cfg", common)
        self.assertIn("/etc/klipper/config/extras-readonly/canvas-common.cfg", common)
        self.assertEqual(set(common) & set(cb2), set())
        self.assertEqual(cb2["/usr/lib/klipper/reset-usb.sh"], "-rwxr-xr-x")
        self.assertEqual(cb2["/etc/sudoers.d/oc-board-config-cb2"], "-r--r-----")
        klipper_version = package_field(self.klipper, "Version").strip()
        afc_version = package_field(self.afc, "Version").strip()
        self.assertEqual(
            package_field(self.common, "Breaks").strip(),
            f"klipper (<< {klipper_version})",
        )
        self.assertEqual(
            package_field(self.cb2, "Breaks").strip(),
            f"afc (<< {afc_version})",
        )
        for old, new in ((f"{klipper_version}~old", klipper_version),
                         (f"{afc_version}~old", afc_version)):
            self.assertEqual(run("dpkg", "--compare-versions", old, "lt", new).returncode, 0)
            self.assertEqual(subprocess.run(
                ["dpkg", "--compare-versions", new, "lt", new]
            ).returncode, 1)
        self.assertIn("ucf", package_field(self.common, "Depends"))
        self.assertIn("afc", package_field(self.cb2, "Depends"))
        run("visudo", "-cf", str(self.cb2_root / "etc/sudoers.d/oc-board-config-cb2"))
        run("sh", "-n", str(self.control / "postinst"))

    def test_printer_config_is_persistent_and_keeps_local_changes(self):
        template = self.common_root / "usr/share/oc-board-config/printer.cfg"
        live = self.config / "printer.cfg"
        self.assertFalse(live.exists())
        run("ucf", "--debconf-ok", str(template), str(live))
        self.assertEqual(live.read_bytes(), template.read_bytes())
        local = template.read_text() + "# local user configuration\n"
        live.write_text(local)
        changed = template.parent / "printer.cfg.new"
        changed.write_text(template.read_text() + "# maintainer change\n")
        env = os.environ.copy()
        env["DEBIAN_FRONTEND"] = "noninteractive"
        run("ucf", "--debconf-ok", str(changed), str(live), env=env)
        self.assertEqual(live.read_text(), local)
        self.assertFalse((self.control / "postrm").exists())

    def test_extracted_config_parses_with_canvas_off_and_on(self):
        parse_config = pathlib.Path(self.tmp.name) / "parse-config"
        shutil.copytree(self.config, parse_config)
        shutil.copy(
            self.common_root / "usr/share/oc-board-config/printer.cfg",
            parse_config / "printer.cfg",
        )
        package = types.ModuleType("klippy")
        package.__path__ = [str(KALICO / "klippy")]
        sys.modules["klippy"] = package
        configfile = importlib.import_module("klippy.configfile")

        class FakeGcode:
            def __init__(self):
                self.ready_gcode_handlers = {}

            def register_command(self, *args, **kwargs):
                pass

        class FakePrinter:
            def __init__(self):
                self.gcode = FakeGcode()

            def lookup_object(self, name):
                assert name == "gcode"
                return self.gcode

        def parse():
            return configfile.PrinterConfig(FakePrinter()).read_config(
                str(parse_config / "printer.cfg")
            ).fileconfig

        off = parse()
        self.assertFalse(off.has_section("mcu canvas"))
        self.assertTrue(off.has_section("gcode_macro RESET_USB"))
        self.assertEqual(off.get("mcu bed", "serial"), "/dev/ttyS0")
        (parse_config / "klipper-readonly/zextras.cfg").write_text(
            "[include ../extras-readonly/canvas.cfg]\n"
        )
        on = parse()
        self.assertTrue(on.has_section("mcu canvas"))
        self.assertTrue(on.get("mcu canvas", "serial").endswith("0:1.2:1.0"))
        self.assertFalse(on.has_section("filament_switch_sensor filament_sensor"))


if __name__ == "__main__":
    unittest.main()
