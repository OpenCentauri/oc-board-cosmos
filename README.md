# oc-board-cosmos

Debian packages of the OpenCentauri Cosmos printer stack for Armbian on Debian 13 (Trixie), `arm64`.

This repository checks out [OpenCentauri/cosmos](https://github.com/OpenCentauri/cosmos) `main`, applies the patches shipped beside those recipes, and builds `.deb` packages with `dpkg-buildpackage` inside Debian Trixie `arm64`.

## Packages

| Package | Contents |
|---|---|
| `klipper` | Kalico `klippy`, compiled `c_helper.so`, and native systemd service. Provides the `klipper` package name. |
| `grumpyscreen` | Native touch UI, built from the revision pinned by Cosmos. |
| `moonraker` | Moonraker plus the Cosmos patches and native systemd service. |
| `fluidd` | Static web UI. |
| `mainsail` | Static web UI. |
| `afc` | AFC-Klipper-Add-On extras and optional AFC/BoxTurtle/RFID configuration files. |
| `tmc-autotune` | TMC stepper autotuning extra and motor database. |
| `addon` | Cosmos addon manager with systemd service restarts. |
| `cosmos-config` | `cosmos.conf` manager, generated fragments, and daemon prestart helpers. |
| `cosmos-mcu-flash` | Prebuilt CC1 bed/toolhead/Canvas Kalico and Katapult payloads with gated flash units. |
| `oc-board-config-common` | Shared CC1 + OpenCentauri board printer configuration and optional Canvas payloads. |
| `oc-board-config-cb2` | CB2 host paths, optional Canvas wrapper, and the manual `RESET_USB` recovery helper. |
| `cosmos` | Metapackage depending on the packages above. |

`cosmos-config` intentionally depends on the separately maintained `oc-board-config-common` package. The `cosmos` metapackage selects `oc-board-config-cb2` for the tested BTT CB2 host. Together they provide `printer.cfg` and the static readonly configuration under `/etc/klipper/config`; this repository does not generate those static files.

Firmware units are enabled at boot but never started or restarted by package installation or upgrade. Flashing requires an `/etc/mcu-flash-enable` file and the expected device. OC-board Katapult entry is not solved yet; the scripts retain the existing fallback flow without the unsupported stock GPIO operations.

Python dependencies are declared on the packages that consume them:
`klipper`, `afc`, `tmc-autotune`, and `moonraker`. Moonraker also declares `curl`, because the
selected upstream recipe and startup/update paths use it. Trixie packages
are used for modules already in the Trixie index. The custom Debian binary
packages `python3-inotify-simple`, `python3-preprocess-cancellation`,
`python3-streaming-form-data`, and `python3-apprise` are built from the
selected Moonraker source's exact or bounded PyPI metadata. Downloads are
verified against PyPI SHA-256 metadata and safely unpacked.

`python3-inotify` is not used for Moonraker's `inotify_simple` import:
it is a separate Python module/package. Moonraker's `msgspec` and `uvloop`
dependencies are compatible with Trixie's `python3-msgspec` 0.19.0 and
`python3-uvloop` 0.21.0 in package metadata terms; the exact upstream
compatibility matrix beyond those package versions was not hardware-tested
in this environment. Optional notification backend features are provided
through `apprise`. Optional Moonraker speedups are declared because the
selected Cosmos recipe lists `msgspec` and `uvloop`.

## Install

```bash
echo 'deb [trusted=yes] https://opencentauri.github.io/oc-board-cosmos/trixie/arm64 ./' \
  | sudo tee /etc/apt/sources.list.d/oc-board-cosmos.list
sudo apt update
sudo apt install cosmos
```

The archive is unsigned for now. `trusted=yes` is required.

## Configuration

The `cosmos` metapackage currently selects `oc-board-config-cb2`. The common
package creates `/etc/klipper/config/printer.cfg` from its template with `ucf`;
local changes default to being retained on upgrade, and the file survives package
removal and purge.

On CB2, `RESET_USB` manually rebinds the USB controller. All USB devices
disconnect briefly, including any attached storage, cameras, and MCUs.

## Rebuilds

GitHub Actions polls `OpenCentauri/cosmos` `main` daily and also runs on `workflow_dispatch` and pushes to this repository. A publish is skipped only when both the recorded Cosmos SHA and a fingerprint of the packaging inputs are unchanged.

## Build caches and offline rebuilds

Local builds persist compiler caches, pinned sources, download archives, and Cargo inputs under `~/.cache/oc-board-cosmos` by default. Set `CACHE_DIR` to override this location. GitHub restores the compiler/download/Cargo caches before building and saves a new snapshot only after a successful build.

Warm an exact local Cosmos checkout using a locally built arm64 builder image:

```bash
COSMOS_DIR="$PWD/../cosmos"
COSMOS_SHA=$(git -C "$COSMOS_DIR" rev-parse HEAD)
DOCKER_PULL=0 BUILDER_IMAGE=oc-board-cosmos-builder:local \
  COSMOS_DIR="$COSMOS_DIR" APT_CHANNEL=nightly PACKAGE_BUILD_NUMBER=0 \
  bash scripts/build-debs.sh "$COSMOS_SHA"
```

Then rebuild the same pin without network access:

```bash
COSMOS_DIR="$PWD/../cosmos"
COSMOS_SHA=$(git -C "$COSMOS_DIR" rev-parse HEAD)
OFFLINE=1 BUILDER_IMAGE=oc-board-cosmos-builder:local \
  COSMOS_DIR="$COSMOS_DIR" APT_CHANNEL=nightly PACKAGE_BUILD_NUMBER=0 \
  bash scripts/build-debs.sh "$COSMOS_SHA"
```

Offline mode runs the package container with `--network none` and fails if any required source or download was not cached by an earlier online build. Rebuilding the builder image itself still requires network access unless its base image and APT inputs are managed separately.
