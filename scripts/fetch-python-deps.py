#!/usr/bin/env python3
"""Build missing Moonraker Python dependencies from pins in the selected source."""

import hashlib
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile

from input_cache import download


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MOONRAKER = "/upstream/moonraker"
OUT = "/tmp/python-deps"


def read_requirements():
    path = os.path.join(MOONRAKER, "pyproject.toml")
    if not os.path.exists(path):
        raise SystemExit(f"missing Moonraker metadata: {path}")
    text = open(path, encoding="utf-8").read()
    block = re.search(r"dependencies\s*=\s*\[(.*?)\]", text, re.S)
    if not block:
        raise SystemExit("missing project dependencies in Moonraker pyproject.toml")
    return block.group(1)


def version_key(value):
    parts = re.split(r"([0-9]+)", value)
    return tuple(int(part) if part.isdigit() else part for part in parts)


def requirement_version(requirements, dist):
    match = re.search(r'["\']' + re.escape(dist) + r'([^"\']*)["\']', requirements)
    if not match:
        raise SystemExit(f"{dist} is not declared in selected Moonraker pyproject.toml")
    spec = match.group(1)
    exact = re.fullmatch(r"==([0-9][0-9A-Za-z.+!-]*)", spec)
    if exact:
        return exact.group(1)
    bounds = re.findall(r"(>=|<=|>|<)\s*([0-9][0-9A-Za-z.+!-]*)", spec)
    lower = [value for op, value in bounds if op == ">="]
    upper = [value for op, value in bounds if op == "<="]
    if not upper:
        raise SystemExit(f"cannot derive bounded version for {dist}: {spec}")
    # Moonraker's upper-bound is compatibility-tested by upstream metadata.
    # For exact pins, return the pin.  Otherwise choose the highest release
    # allowed by the selected upstream range.
    upper = upper[0]
    lower = lower[0] if lower else None
    data = json.loads(download(f"https://pypi.org/pypi/{dist}/json"))
    candidates = []
    for value in data["releases"]:
        if re.fullmatch(r"[0-9]+(?:\.[0-9]+)*(?:[A-Za-z0-9.+!-]*)", value):
            if lower and version_key(value) < version_key(lower):
                continue
            if version_key(value) > version_key(upper):
                continue
            candidates.append(value)
    if not candidates:
        raise SystemExit(f"no PyPI release for {dist} within {spec}")
    return max(candidates, key=version_key)


def safe_extract(archive, dest):
    if archive.endswith(".zip"):
        with zipfile.ZipFile(archive) as handle:
            for member in handle.infolist():
                target = os.path.realpath(os.path.join(dest, member.filename))
                if os.path.commonpath((dest, target)) != dest:
                    raise SystemExit(f"unsafe archive path: {member.filename}")
                if member.external_attr >> 16 & 0o170000 == 0o120000:
                    raise SystemExit(f"unsafe archive symlink: {member.filename}")
            handle.extractall(dest)
        return
    with tarfile.open(archive, "r:*") as handle:
        for member in handle.getmembers():
            target = os.path.realpath(os.path.join(dest, member.name))
            if os.path.commonpath((dest, target)) != dest:
                raise SystemExit(f"unsafe archive path: {member.name}")
            if member.issym() or member.islnk():
                raise SystemExit(f"unsafe archive link: {member.name}")
        handle.extractall(dest)


def fetch_sdist(dist, version, dest):
    data = json.loads(download(f"https://pypi.org/pypi/{dist}/{version}/json"))
    sdist = next((item for item in data["urls"]
                   if item["packagetype"] == "sdist"), None)
    if not sdist:
        raise SystemExit(f"no sdist for {dist} {version}")
    archive = os.path.join(OUT, sdist["filename"])
    os.makedirs(OUT, exist_ok=True)
    with open(archive, "wb") as handle:
        handle.write(download(sdist["url"]))
    got = hashlib.sha256(open(archive, "rb").read()).hexdigest()
    if got != sdist["digests"]["sha256"]:
        raise SystemExit(
            f"{dist} sha256 mismatch: got {got}, expected {sdist['digests']['sha256']}")
    print(f"pin {dist}: {version} {sdist['url']} sha256={got}", flush=True)
    os.makedirs(dest, exist_ok=True)
    safe_extract(archive, dest)


def find_unpacked_root(dest):
    entries = [os.path.join(dest, name) for name in os.listdir(dest)
               if os.path.isdir(os.path.join(dest, name))]
    if len(entries) != 1:
        raise SystemExit(f"unexpected sdist layout in {dest}")
    return entries[0]


def main():
    requirements = read_requirements()
    specs = {
        "inotify-simple": ("python3-inotify-simple", "inotify-simple"),
        "preprocess-cancellation": ("python3-preprocess-cancellation",
                                    "preprocess-cancellation"),
        "streaming-form-data": ("python3-streaming-form-data",
                                "streaming-form-data"),
        "apprise": ("python3-apprise", "apprise"),
    }
    os.makedirs(OUT, exist_ok=True)
    versions = []
    for dist, (package, pyproject_dist) in specs.items():
        version = requirement_version(requirements, pyproject_dist)
        work = os.path.join(OUT, package)
        shutil.rmtree(work, ignore_errors=True)
        os.makedirs(work)
        fetch_sdist(pyproject_dist, version, work)
        root = find_unpacked_root(work)
        shutil.copytree(os.path.join(ROOT, "packages", package, "debian"),
                        os.path.join(root, "debian"))
        changelog = os.path.join(root, "debian", "changelog")
        with open(changelog, "w", encoding="utf-8") as handle:
            handle.write(
                f"{package} ({version}-1) trixie; urgency=medium\n\n"
                f"  * Package selected upstream release {version}\n\n"
                " -- OpenCentauri Project <noreply@opencentauri.github.io>  "
                "Sun, 22 Nov 2026 13:01:54 +0000\n")
        os.chmod(os.path.join(root, "debian", "rules"), 0o755)
        os.makedirs("/tmp/custom-python-deps", exist_ok=True)
        with open("/tmp/package-versions", "a", encoding="utf-8") as handle:
            handle.write(f"{package} {version}\n")
        versions.append((package, root))

    if not os.path.exists("/tmp/package-versions"):
        open("/tmp/package-versions", "w").close()
    for package, root in versions:
        print(f"building {package}", flush=True)
        subprocess.check_call(["dpkg-buildpackage", "-us", "-uc", "-b"], cwd=root)
        for deb in glob.glob(os.path.join(os.path.dirname(root), "*.deb")):
            shutil.copy2(deb, "/tmp/custom-python-deps/")


if __name__ == "__main__":
    main()
