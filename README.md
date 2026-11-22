# oc-board-cosmos

Debian packages of the OpenCentauri Cosmos printer stack for Armbian on Debian 13 (Trixie), `arm64`.

This repository checks out [OpenCentauri/cosmos](https://github.com/OpenCentauri/cosmos) `main`, applies the patches shipped beside those recipes, and builds `.deb` packages with `dpkg-buildpackage` inside Debian Trixie `arm64`.

## Packages

| Package | Contents |
|---|---|
| `klipper` | Kalico `klippy`, compiled `c_helper.so`, SysV init. Provides the `klipper` package name. |
| `grumpyscreen` | Native touch UI, built from the revision pinned by Cosmos. |
| `moonraker` | Moonraker plus the Cosmos patches under `recipes-apps/moonraker/files`. |
| `fluidd` | Static web UI. |
| `mainsail` | Static web UI. |
| `afc` | AFC-Klipper-Add-On extras and Cosmos readonly configuration files. |
| `tmc-autotune` | TMC stepper autotuning extra and motor database. |
| `cosmos` | Metapackage depending on the packages above. |

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

## Rebuilds

GitHub Actions polls `OpenCentauri/cosmos` `main` daily and also runs on `workflow_dispatch` and pushes to this repository. A publish is skipped only when both the recorded Cosmos SHA and a fingerprint of the packaging inputs are unchanged.
