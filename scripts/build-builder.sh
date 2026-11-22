#!/bin/bash
set -euo pipefail
image="ghcr.io/${GITHUB_REPOSITORY,,}:builder"
base=ghcr.io/armbian/docker-armbian-build:armbian-debian-trixie-latest
sha=$(sha256sum Dockerfile | awk '{print $1}')
digest=$(docker buildx imagetools inspect "$base" --format '{{.Manifest.Digest}}')
test -n "$digest"
need=true
if docker pull "$image"; then
  have=$(docker inspect --format '{{index .Config.Labels "org.opencontainers.image.base.digest"}}' "$image")
  have_sha=$(docker inspect --format '{{index .Config.Labels "org.opencontainers.image.dockerfile.sha"}}' "$image")
  if [ "$have" = "$digest" ] && [ "$have_sha" = "$sha" ]; then
    need=false
  fi
fi
if [ "$need" = true ]; then
  docker build --pull --build-arg "BASE_DIGEST=$digest" \
    --label "org.opencontainers.image.dockerfile.sha=$sha" -t "$image" .
  docker push "$image"
fi
echo "image=$image" >> "$GITHUB_OUTPUT"
