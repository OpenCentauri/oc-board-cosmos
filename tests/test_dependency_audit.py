import pathlib
import json
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class DependencyAuditTests(unittest.TestCase):
    def test_consumers_have_audited_dependencies(self):
        klipper = (ROOT / "packages/klipper/debian/control").read_text()
        moonraker = (ROOT / "packages/moonraker/debian/control").read_text()
        flashtool = (ROOT / "packages/flashtool/debian/control").read_text()

        for name in ("python3-cffi", "python3-greenlet", "python3-markupsafe",
                     "python3-can", "python3-msgspec"):
            self.assertIn(name, klipper)
        for name in ("python3-tornado", "python3-serial-asyncio",
                     "python3-streaming-form-data", "python3-distro",
                     "python3-inotify-simple", "python3-preprocess-cancellation",
                     "python3-dbus-fast", "python3-apprise", "python3-ldap3",
                     "python3-msgspec", "python3-uvloop", "python3-aiofiles",
                     "curl"):
            self.assertIn(name, moonraker)
        self.assertIn("python3-serial", flashtool)
        self.assertNotIn("python3-inotify,", moonraker)

    def test_custom_native_package_has_arm64_architecture(self):
        control = (ROOT / "packages/python3-streaming-form-data/debian/control").read_text()
        self.assertIn("Architecture: arm64", control)
        for name in ("python3-inotify-simple", "python3-preprocess-cancellation",
                     "python3-apprise"):
            control = (ROOT / "packages" / name / "debian/control").read_text()
            self.assertIn("Architecture: all", control)

    def test_custom_dependencies_are_pin_derived_and_not_latest_floating(self):
        script = (ROOT / "scripts/fetch-python-deps.py").read_text()
        self.assertIn("pyproject.toml", script)
        self.assertIn("allowed by the selected upstream range", script)
        self.assertIn('sdist["digests"]["sha256"]', script)

    def test_release_fixtures_are_distinct_and_keep_pre_cutoff_empty(self):
        before = json.loads((ROOT / "tests/fixtures/release-before-cutoff.json").read_text())
        eligible = json.loads((ROOT / "tests/fixtures/release-eligible.json").read_text())
        cutoff = "2026-11-22T12:33:00+00:00"
        self.assertLess(before["published_at"], cutoff)
        self.assertGreater(eligible["published_at"], cutoff)



if __name__ == "__main__":
    unittest.main()
