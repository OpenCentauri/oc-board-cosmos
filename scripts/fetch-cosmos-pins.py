#!/usr/bin/env python3
"""Fetch sources pinned by meta-opencentauri and record package versions.

Call it from the builder container:

    python3 scripts/fetch-cosmos-pins.py \
        kalico moonraker grumpyscreen fluidd mainsail ustreamer \
        /cosmos/meta-opencentauri

Arguments are recipe names followed by the meta-opencentauri directory.
Git recipes are cloned and patched under /upstream/<name>. Zip recipes are
downloaded, verified, and unpacked there. Package versions are written to
/tmp/package-versions for the Debian changelog rewrite.
"""

import glob
import hashlib
import os
import re
import shutil
import subprocess
import sys

from input_cache import download, offline


def version_key(path):
    """Return a sort key for a recipe path so the highest version wins.

    Called by recipe_files(). The version is the part after the underscore in
    the filename, for example kalico_2026.02.00.bb.
    """
    stem = os.path.basename(path).rsplit(".", 1)[0]
    version = stem.split("_", 1)[1] if "_" in stem else "0"
    return [int(part) if part.isdigit() else part for part in re.split(r"([0-9]+)", version)]


def recipe_files(root, name):
    """Return name_*.bb and name_*.inc paths under root, highest version last.

    Called as recipe_files(root, "kalico"). Hyphenated names such as
    kalico-firmware-bed_*.bb do not match.
    """
    found = glob.glob(os.path.join(root, "recipes-*", "*", f"{name}_*.bb"))
    found += glob.glob(os.path.join(root, "recipes-*", "*", f"{name}_*.inc"))
    if not found:
        sys.exit(f"no {name}_* recipe under {root}")
    return sorted(found, key=version_key)


def recipe_version(root, name):
    """Return the version from the highest name_* recipe filename.

    Called as recipe_version(root, "fluidd"), which returns "1.37.4" for
    fluidd_1.37.4.bb.
    """
    return os.path.basename(recipe_files(root, name)[-1]).split("_", 1)[1].rsplit(".", 1)[0]


def recipe_text(root, name):
    """Return the selected recipe path, its text, and its filename version.

    Called by fetch_git() and fetch_zip(). If the .bb only require's an .inc
    and has no SRCREV, the include text is appended so the pin can be read.
    """
    ordered = recipe_files(root, name)
    recipe = ordered[-1]
    with open(recipe) as handle:
        text = handle.read().replace("\\\n", "")
    require = re.search(r"^require\s+(\S+)", text, re.M)
    if require and "SRCREV" not in text:
        inc = os.path.join(os.path.dirname(recipe), require.group(1))
        if os.path.exists(inc):
            text += "\n" + open(inc).read().replace("\\\n", "")
            recipe = inc
    return recipe, text, recipe_version(root, name)


def checkout_git(url, rev, dest, name, submodules=False):
    """Reuse a cached checkout when possible, without silently using another pin."""
    if not os.path.exists(os.path.join(dest, ".git")):
        if offline():
            sys.exit(f"offline source missing: {name}@{rev}; run an online build first")
        subprocess.check_call(["git", "clone", url, dest])
    subprocess.check_call(["git", "-C", dest, "remote", "set-url", "origin", url])
    present = subprocess.run(
        ["git", "-C", dest, "cat-file", "-e", f"{rev}^{{commit}}"], check=False).returncode == 0
    if not present:
        if offline():
            sys.exit(f"offline source missing: {name}@{rev}; run an online build first")
        subprocess.check_call(["git", "-C", dest, "fetch", "origin", rev])
    subprocess.check_call(["git", "-C", dest, "checkout", "--force", "--detach", rev])
    subprocess.check_call(["git", "-C", dest, "reset", "--hard", rev])
    subprocess.check_call(["git", "-C", dest, "clean", "-fdx"])
    if submodules:
        subprocess.check_call(["git", "-C", dest, "submodule", "sync", "--recursive"])
        command = ["git", "-C", dest, "submodule", "update", "--init", "--recursive", "--force"]
        if offline():
            command.append("--no-fetch")
        subprocess.check_call(command)
        subprocess.check_call(
            ["git", "-C", dest, "submodule", "foreach", "--recursive", "git", "clean", "-fdx"])


def fetch_git(root, name):
    """Clone the recipe's git pin, check out SRCREV, and apply files/*.patch.

    Called as fetch_git(root, "kalico"). GrumpyScreen also updates submodules.
    The result is /upstream/<name>.
    """
    recipe, text, version = recipe_text(root, name)
    uri = re.search(r"(?:git|gitsm)://([^;\s\"]+)", text)
    rev = re.search(r'SRCREV\s*=\s*"([0-9a-fA-F]+)"', text)
    if not uri or not rev:
        sys.exit(f"missing git pin in {recipe}")
    dest = f"/upstream/{name}"
    print(f"pin {name}: {version} https://{uri.group(1)} @ {rev.group(1)}", flush=True)
    checkout_git(f"https://{uri.group(1)}", rev.group(1), dest, name, name == "grumpyscreen")
    got = subprocess.check_output(["git", "-C", dest, "rev-parse", "HEAD"], text=True).strip()
    if got.lower() != rev.group(1).lower():
        sys.exit(f"{name} revision mismatch: got {got}, expected {rev.group(1)}")
    files_dir = os.path.join(os.path.dirname(recipe), "files")
    for patch_file in sorted(glob.glob(os.path.join(files_dir, "*.patch"))):
        subprocess.check_call(["patch", "-d", dest, "-p1", "-i", patch_file])


def fetch_zip(root, name):
    """Download the recipe's release zip, verify sha256, and unpack it.

    Called as fetch_zip(root, "fluidd"). ${PV} in the URL is replaced with the
    recipe filename version. The result is /upstream/<name>.
    """
    recipe, text, version = recipe_text(root, name)
    uri = re.search(r"https://[^;\s\"]+\.zip", text)
    digest = re.search(r'SRC_URI\[sha256sum\]\s*=\s*"([0-9a-fA-F]+)"', text)
    if not uri or not digest:
        sys.exit(f"missing release zip pin in {recipe}")
    url = uri.group(0).replace("${PV}", version)
    dest = f"/upstream/{name}"
    archive = f"/tmp/{name}.zip"
    print(f"pin {name}: {version} {url}", flush=True)
    with open(archive, "wb") as handle:
        handle.write(download(url))
    got = hashlib.sha256(open(archive, "rb").read()).hexdigest()
    if got != digest.group(1):
        sys.exit(f"{name} sha256 mismatch for {url}: {got} != {digest.group(1)}")
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest, exist_ok=True)
    subprocess.check_call(["unzip", "-q", archive, "-d", dest])


def cosmos_version(root):
    """Return DISTRO_VERSION from conf/distro/cosmos.conf.

    Called as cosmos_version(root). This is the version of the cosmos
    metapackage, not a recipe filename version.
    """
    path = os.path.join(root, "conf", "distro", "cosmos.conf")
    text = open(path).read()
    match = re.search(r'^DISTRO_VERSION\s*=\s*"([^"]+)"', text, re.M)
    if not match:
        sys.exit(f"missing DISTRO_VERSION in {path}")
    return match.group(1)


def main():
    """Fetch every named recipe and write /tmp/package-versions.

    Called by the script entry point. The last argument is the
    meta-opencentauri directory. Earlier arguments are recipe names to fetch.
    """
    if len(sys.argv) < 3:
        sys.exit("usage: fetch-cosmos-pins.py NAME... META_OPENCENTAURI_DIR")
    root = sys.argv[-1]
    names = sys.argv[1:-1]
    os.makedirs("/upstream", exist_ok=True)
    versions = {
        "klipper": recipe_version(root, "kalico"),
        "moonraker": recipe_version(root, "moonraker"),
        "grumpyscreen": recipe_version(root, "grumpyscreen"),
        "fluidd": recipe_version(root, "fluidd"),
        "mainsail": recipe_version(root, "mainsail"),
        "ustreamer": recipe_version(root, "ustreamer"),
        "afc": recipe_version(root, "afc"),
        "tmc-autotune": recipe_version(root, "tmc-autotune"),
        "addon": recipe_version(root, "addon"),
        "cosmos-config": recipe_version(root, "config-manager"),
        "cosmos-mcu-flash": recipe_version(root, "kalico-firmware-bed"),
        "cosmos": cosmos_version(root),
    }
    versions["oc-board-config"] = versions["cosmos"]
    with open("/tmp/package-versions", "w") as handle:
        for name, version in versions.items():
            print(f"version {name}: {version}", flush=True)
            handle.write(f"{name} {version}\n")
    for name in names:
        _recipe, text, _version = recipe_text(root, name)
        if "git://" in text or "gitsm://" in text:
            fetch_git(root, name)
        else:
            fetch_zip(root, name)


if __name__ == "__main__":
    main()
