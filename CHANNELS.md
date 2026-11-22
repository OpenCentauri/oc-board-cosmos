# APT channels

nightly.yml runs on packaging pushes to main, daily at 06:00 UTC, and manual dispatch. It selects Cosmos main, skipping unchanged scheduled builds. Packaging pushes and manual runs can rebuild nightly.

release.yml checks daily at 06:30 UTC or on manual dispatch. It builds only a new published non-prerelease Cosmos release, excluding baseline 26.10.1 (release ID 430278801) and releases published at or before 2026-11-22T12:33:00Z. The release archive remains empty until a future eligible release. Editing the baseline release does not populate it. Packaging pushes do not trigger release builds. Manual dispatch checks eligibility; it does not force rebuilding a published release.

Both call apt-trixie-arm64.yml, a reusable workflow. It resolves the exact source commit, refreshes the shared builder if necessary, builds packages, and publishes to a channel-specific directory. Pins, patches and configs are extracted from the selected Cosmos checkout, not unconditionally from main. Annotated release tags are resolved to their commit. Failed builds leave the published marker unchanged for retry. A shared concurrency group serializes the build and publication across channels.

Select ONE flat APT source:

```
deb [trusted=yes arch=arm64] https://opencentauri.github.io/oc-board-cosmos/nightly/trixie/arm64/ ./
```

After the first eligible release is successfully published:

```
deb [trusted=yes arch=arm64] https://opencentauri.github.io/oc-board-cosmos/release/trixie/arm64/ ./
```

The archives are unsigned: trusted=yes bypasses APT signature verification. Switching channels may require explicit version selection or downgrades. Do not enable both expecting automatic channel preference.

The legacy trixie/arm64 path is retained but frozen. Existing clients must switch to the nightly URL to receive further builds. There is no release APT index before the first eligible publication.

Each channel has its own build.json and cosmos-sha. Versions include channel, workflow run number and Cosmos commit. build.json also records a packaging fingerprint covering package definitions and build scripts. Changes to packaging therefore rebuild even if the selected Cosmos SHA is unchanged. Old package files may remain on Pages, but current indexes are regenerated from the current build output. Scheduled polling needs no changes in Cosmos upstream; an upstream release event does not directly trigger this repository.

Pull requests do not publish or build the shared image. These channel entry points deliberately have no pull_request trigger.
