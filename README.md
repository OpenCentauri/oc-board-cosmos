# oc-board-cosmos

Debian packages of the OpenCentauri Cosmos printer stack for Armbian on Debian 13 (Trixie), `arm64`.

This is not an Isar or OpenEmbedded layer. `meta-opencentauri` recipes cannot be executed by Isar. This repository checks out [OpenCentauri/cosmos](https://github.com/OpenCentauri/cosmos) `main`, applies the patches shipped beside those recipes, and builds `.deb` packages with `dpkg-buildpackage` inside Debian Trixie `arm64`.

## Packages

| Package | Contents |
|---|---|
| `klipper` | Kalico `klippy`, compiled `c_helper.so`, SysV init. Provides the `klipper` package name. |
| `grumpyscreen` | Native touch UI, built from the revision pinned by Cosmos. |
| `moonraker` | Moonraker plus the Cosmos patches under `recipes-apps/moonraker/files`. |
| `fluidd` | Static web UI. |
| `mainsail` | Static web UI. |
| `cosmos` | Metapackage depending on the five packages above. |

## Install

```bash
echo 'deb [trusted=yes] https://opencentauri.github.io/oc-board-cosmos/trixie/arm64 ./' \
  | sudo tee /etc/apt/sources.list.d/oc-board-cosmos.list
sudo apt update
sudo apt install cosmos
```

The archive is unsigned for now. `trusted=yes` is required.

## Rebuilds

GitHub Actions polls `OpenCentauri/cosmos` `main` daily and also runs on `workflow_dispatch` and pushes to this repository. A publish is skipped when the recorded Cosmos SHA has not changed.
