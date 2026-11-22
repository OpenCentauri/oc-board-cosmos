import importlib.util
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_fetch_script():
    spec = importlib.util.spec_from_file_location(
        "fetch_cosmos_pins", ROOT / "scripts/fetch-cosmos-pins.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CosmosAddonTests(unittest.TestCase):
    def test_recipe_pin_extraction_finds_recipes_data(self):
        module = load_fetch_script()
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            recipe_dir = root / "recipes-data" / "klipper-afc-addon"
            recipe_dir.mkdir(parents=True)
            recipe = recipe_dir / "afc_0.1.bb"
            recipe.write_text(
                'SRC_URI = "git://github.com/suchmememanyskill/AFC-Klipper-Add-On.git;protocol=https"\n'
                'SRCREV = "0fd50f2229b685cdb9b84793150ab0798e16eb03"\n')
            selected, text, version = module.recipe_text(str(root), "afc")
            self.assertEqual(pathlib.Path(selected), recipe)
            self.assertEqual(version, "0.1")
            self.assertIn("0fd50f2229b685cdb9b84793150ab0798e16eb03", text)

    def test_build_inside_addons_and_versions_are_integrated(self):
        build = (ROOT / "scripts/build-inside.sh").read_text()
        fetch = (ROOT / "scripts/fetch-cosmos-pins.py").read_text()
        self.assertIn("afc tmc-autotune", build)
        self.assertIn("afc tmc-autotune mcu-flasher", build)
        self.assertIn('"afc":', fetch)
        self.assertIn('"tmc-autotune":', fetch)

    def test_generated_package_metadata_and_paths(self):
        afc_control = (ROOT / "packages/afc/debian/control").read_text()
        tmc_control = (ROOT / "packages/tmc-autotune/debian/control").read_text()
        cosmos_control = (ROOT / "packages/cosmos/debian/control").read_text()
        afc_rules = (ROOT / "packages/afc/debian/rules").read_text()
        tmc_rules = (ROOT / "packages/tmc-autotune/debian/rules").read_text()

        self.assertIn("Architecture: all", afc_control)
        self.assertIn("Depends: ${misc:Depends}, klipper, python3", afc_control)
        self.assertIn("Architecture: all", tmc_control)
        self.assertIn("Depends: ${misc:Depends}, klipper, python3", tmc_control)
        self.assertIn("Depends: klipper, afc, tmc-autotune", cosmos_control)

        self.assertIn("/usr/share/klipper/klippy/extras", afc_rules)
        self.assertIn("! -name '__init__.py'", afc_rules)
        for config in ("afc.cfg", "canvas.cfg", "boxturtle.cfg", "canvas_rfid.cfg"):
            self.assertIn(config, afc_rules)
        self.assertIn("/etc/klipper/config/extras-readonly", afc_rules)

        for payload in ("autotune_tmc.py", "motor_constants.py", "motor_database.cfg"):
            self.assertIn(payload, tmc_rules)
        self.assertIn("/usr/share/klipper/klippy/extras", tmc_rules)

    def test_packaging_fingerprint_invalidates_unchanged_cosmos(self):
        select = (ROOT / "scripts/select-channel.py").read_text()
        module = load_fetch_script()
        self.assertIn("packaging_fingerprint", select)
        self.assertIn("previous.get('packaging_fingerprint')", select)

    def test_pinned_source_payload_and_imports_exist(self):
        afc = pathlib.Path("/tmp/afc-source")
        tmc = pathlib.Path("/tmp/tmc-source")
        self.assertFalse((afc / "extras/__init__.py").is_symlink())
        self.assertTrue((afc / "extras/AFC.py").is_file())
        self.assertTrue((tmc / "autotune_tmc.py").is_file())
        self.assertTrue((tmc / "motor_constants.py").is_file())
        self.assertTrue((tmc / "motor_database.cfg").is_file())


if __name__ == "__main__":
    unittest.main()
