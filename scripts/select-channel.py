#!/usr/bin/env python3
"""Resolve a channel's exact Cosmos commit; do not rebuild published releases."""
import datetime
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
import hashlib
import pathlib


def packaging_fingerprint():
    """Fingerprint repository inputs that affect generated Debian packages."""
    root = pathlib.Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    paths = [
        root / 'Dockerfile',
        root / 'scripts/fetch-cosmos-pins.py',
        root / 'scripts/build-inside.sh',
        root / 'scripts/build-debs.sh',
        root / 'scripts/stage-apt.sh',
        root / 'scripts/select-channel.py',
    ]
    paths += sorted((root / 'packages').glob('*/debian/**/*'))
    for path in paths:
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b'\0')
            digest.update(path.read_bytes())
    return digest.hexdigest()


fingerprint = packaging_fingerprint()

channel = os.environ['APT_CHANNEL']
if channel not in ('nightly', 'release'):
    raise SystemExit('Invalid APT_CHANNEL')
result = subprocess.run(['git', 'show', f'origin/gh-pages:{channel}/trixie/arm64/build.json'], capture_output=True, text=True)
previous = json.loads(result.stdout) if result.returncode == 0 else {}


def resolve(ref):
    text = subprocess.check_output(['git', 'ls-remote', 'https://github.com/OpenCentauri/cosmos.git', ref, ref + '^{}'], text=True)
    refs = dict((line.split()[1], line.split()[0]) for line in text.splitlines())
    sha = refs.get(ref + '^{}', refs.get(ref, ''))
    if not re.fullmatch('[0-9a-f]{40}', sha):
        raise RuntimeError(f'Cannot resolve {ref}')
    return sha


def nightly_should_build(sha, previous, event_name, fingerprint):
    return (previous.get('sha') != sha
            or previous.get('packaging_fingerprint') != fingerprint
            or event_name in ('push', 'workflow_dispatch'))


def eligible_release(release, previous, cutoff='2026-11-22T12:33:00+00:00',
                     excluded_id='430278801'):
    if not release or release.get('draft') or release.get('prerelease'):
        return None
    published = datetime.datetime.fromisoformat(
        release['published_at'].replace('Z', '+00:00'))
    cutoff = datetime.datetime.fromisoformat(cutoff)
    release_id = str(release['id'])
    if release_id == excluded_id:
        return None
    if published <= cutoff:
        return None
    if (str(previous.get('release_id', '')) == release_id
            and previous.get('packaging_fingerprint') == fingerprint):
        return None
    return release_id


outputs = dict(build='false', sha='', release_id='', tag='', packaging_fingerprint=fingerprint)
if channel == 'nightly':
    sha = resolve('refs/heads/main')
    if nightly_should_build(sha, previous, os.environ['GITHUB_EVENT_NAME'], fingerprint):
        outputs.update(build='true', sha=sha)
else:
    request = urllib.request.Request('https://api.github.com/repos/OpenCentauri/cosmos/releases/latest', headers={'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'], 'Accept': 'application/vnd.github+json', 'User-Agent': 'oc-board-cosmos'})
    try:
        with urllib.request.urlopen(request) as response:
            release = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        release = None
    release_id = eligible_release(release, previous)
    if release_id:
        outputs.update(build='true', sha=resolve('refs/tags/' + release['tag_name']),
                       release_id=release_id, tag=release['tag_name'])
with open(os.environ['GITHUB_OUTPUT'], 'a') as handle:
    for key, value in outputs.items():
        if '\n' in value or '\r' in value:
            raise ValueError('Invalid output value')
        handle.write(f'{key}={value}\n')
print(json.dumps(outputs, indent=2))
