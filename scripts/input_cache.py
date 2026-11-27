"""Small persistent URL cache for pinned build inputs."""

import hashlib
import os
from pathlib import Path
import tempfile
import urllib.request


def offline():
    return os.environ.get('OFFLINE') == '1'


def download(url):
    cache = Path(os.environ.get('DOWNLOAD_CACHE', '/cache/downloads'))
    path = cache / hashlib.sha256(url.encode()).hexdigest()
    if offline():
        if not path.is_file():
            raise SystemExit(f'offline input missing: {url}; run an online build first')
        return path.read_bytes()

    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read()
    cache.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=cache)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    except BaseException:
        os.unlink(temporary)
        raise
    return data
