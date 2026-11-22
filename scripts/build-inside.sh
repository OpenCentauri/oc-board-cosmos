#!/bin/bash
set -euo pipefail

python3 - kalico moonraker grumpyscreen fluidd mainsail /cosmos/meta-opencentauri <<'PY'
import glob, hashlib, os, re, subprocess, sys
names = sys.argv[1:-1]
root = sys.argv[-1]

def version_key(path):
    stem = os.path.basename(path).rsplit(".", 1)[0]
    version = stem.split("_", 1)[1] if "_" in stem else "0"
    return [int(part) if part.isdigit() else part for part in re.split(r"([0-9]+)", version)]

def recipe_version(name):
    found = glob.glob(os.path.join(root, "recipes-apps", "*", f"{name}_*.bb"))
    found += glob.glob(os.path.join(root, "recipes-apps", "*", f"{name}_*.inc"))
    if not found:
        sys.exit(f"no {name}_* recipe under {root}")
    return os.path.basename(sorted(found, key=version_key)[-1]).split("_", 1)[1].rsplit(".", 1)[0]

def recipe_text(name):
    found = glob.glob(os.path.join(root, "recipes-apps", "*", f"{name}_*.bb"))
    found += glob.glob(os.path.join(root, "recipes-apps", "*", f"{name}_*.inc"))
    if not found:
        sys.exit(f"no {name}_* recipe under {root}")
    ordered = sorted(found, key=version_key)
    recipe = ordered[-1]
    text = open(recipe).read().replace("\\\n", "")
    require = re.search(r"^require\s+(\S+)", text, re.M)
    if require and "SRCREV" not in text:
        inc = os.path.join(os.path.dirname(recipe), require.group(1))
        if os.path.exists(inc):
            text += "\n" + open(inc).read().replace("\\\n", "")
            recipe = inc
    return recipe, text, recipe_version(name)

def fetch_git(name):
    recipe, text, version = recipe_text(name)
    uri = re.search(r"(?:git|gitsm)://([^;\s\"]+)", text)
    rev = re.search(r'SRCREV\s*=\s*"([0-9a-fA-F]+)"', text)
    if not uri or not rev:
        sys.exit(f"missing git pin in {recipe}")
    dest = f"/upstream/{name}"
    print(f"pin {name}: {version} https://{uri.group(1)} @ {rev.group(1)}", flush=True)
    subprocess.check_call(["git", "clone", f"https://{uri.group(1)}", dest])
    subprocess.check_call(["git", "-C", dest, "checkout", "--detach", rev.group(1)])
    if name == "grumpyscreen":
        subprocess.check_call(["git", "-C", dest, "submodule", "update", "--init", "--recursive"])
    files_dir = os.path.join(os.path.dirname(recipe), "files")
    for patch_file in sorted(glob.glob(os.path.join(files_dir, "*.patch"))):
        subprocess.check_call(["patch", "-d", dest, "-p1", "-i", patch_file])

def fetch_zip(name):
    recipe, text, version = recipe_text(name)
    uri = re.search(r"https://[^;\s\"]+\.zip", text)
    digest = re.search(r'SRC_URI\[sha256sum\]\s*=\s*"([0-9a-fA-F]+)"', text)
    if not uri or not digest:
        sys.exit(f"missing release zip pin in {recipe}")
    url = uri.group(0).replace("${PV}", version)
    dest = f"/upstream/{name}"
    archive = f"/tmp/{name}.zip"
    print(f"pin {name}: {version} {url}", flush=True)
    subprocess.check_call(["curl", "-fsSL", "-o", archive, url])
    got = hashlib.sha256(open(archive, "rb").read()).hexdigest()
    if got != digest.group(1):
        sys.exit(f"{name} sha256 mismatch for {url}: {got} != {digest.group(1)}")
    os.makedirs(dest, exist_ok=True)
    subprocess.check_call(["unzip", "-q", archive, "-d", dest])

def cosmos_version():
    path = os.path.join(root, "conf", "distro", "cosmos.conf")
    text = open(path).read()
    match = re.search(r'^DISTRO_VERSION\s*=\s*"([^"]+)"', text, re.M)
    if not match:
        sys.exit(f"missing DISTRO_VERSION in {path}")
    return match.group(1)

os.makedirs("/upstream", exist_ok=True)
versions = {
    "klipper": recipe_version("kalico"),
    "moonraker": recipe_version("moonraker"),
    "grumpyscreen": recipe_version("grumpyscreen"),
    "fluidd": recipe_version("fluidd"),
    "mainsail": recipe_version("mainsail"),
    "cosmos": cosmos_version(),
}
with open("/tmp/package-versions", "w") as handle:
    for name, version in versions.items():
        print(f"version {name}: {version}", flush=True)
        handle.write(f"{name} {version}\n")
for name in names:
    _recipe, text, _version = recipe_text(name)
    if "git://" in text or "gitsm://" in text:
        fetch_git(name)
    else:
        fetch_zip(name)
PY

version_suffix="+git${COSMOS_SHA:0:12}~trixie1"
shopt -s nullglob
package_version() {
  awk -v name="$1" '$1 == name { print $2 }' /tmp/package-versions
}
build_pkg() {
  name=$1
  version=$(package_version "$name")
  test -n "$version"
  parent=$(mktemp -d)
  src="$parent/$name"
  mkdir -p "$src"
  cp -a "/src/packages/${name}/." "$src/"
  sed -i "1s/([^)]*)/(${version}${version_suffix})/" "$src/debian/changelog"
  (cd "$src" && dpkg-buildpackage -us -uc -b)
  cp "$parent/"*.deb /src/out/
}

for name in fluidd mainsail moonraker klipper grumpyscreen cosmos; do
  build_pkg "$name"
done
