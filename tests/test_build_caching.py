import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import input_cache

spec = importlib.util.spec_from_file_location('fetch_cosmos_pins', ROOT / 'scripts/fetch-cosmos-pins.py')
fetch_cosmos_pins = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_cosmos_pins)


def read(path):
    return (ROOT / path).read_text()


class BuildCachingTests(unittest.TestCase):
    def test_persistent_compiler_and_input_caches(self):
        dockerfile = read('Dockerfile')
        wrapper = read('scripts/build-debs.sh')
        inside = read('scripts/build-inside.sh')
        self.assertIn('ccache', dockerfile)
        self.assertIn('sccache', dockerfile)
        self.assertIn('/usr/lib/ccache', dockerfile)
        for value in ('CCACHE_DIR=/cache/ccache', 'SCCACHE_DIR=/cache/sccache',
                      'CARGO_HOME=/cache/cargo', 'DOWNLOAD_CACHE=/cache/downloads',
                      'CCACHE_NOHASHDIR=1', 'RUSTC_WRAPPER=sccache'):
            self.assertIn(value, wrapper)
        self.assertIn('CACHE_DIR', wrapper)
        self.assertIn('/upstream', wrapper)
        self.assertIn('ccache --show-stats', inside)
        self.assertIn('sccache --show-stats', inside)

    def test_cargo_target_path_is_stable_and_cleaned(self):
        rules = read('packages/mcu-flasher/debian/rules')
        self.assertIn('CARGO_TARGET_DIR := /tmp/oc-board-mcu-flasher-target', rules)
        self.assertNotIn('CARGO_TARGET_DIR=$(CURDIR)', rules)
        self.assertIn('rm -rf "$(CARGO_TARGET_DIR)"', rules)

    def test_offline_mode_fails_closed(self):
        wrapper = read('scripts/build-debs.sh')
        fetch = read('scripts/fetch-cosmos-pins.py')
        python_deps = read('scripts/fetch-python-deps.py')
        input_cache = read('scripts/input_cache.py')
        self.assertIn('OFFLINE', wrapper)
        self.assertIn('COSMOS_DIR', wrapper)
        self.assertIn('none', wrapper)
        self.assertIn('offline', fetch)
        self.assertIn('--no-fetch', fetch)
        self.assertIn('cat-file', fetch)
        self.assertIn('submodule", "sync"', fetch)
        self.assertIn('from input_cache import download', python_deps)
        self.assertIn('DOWNLOAD_CACHE', input_cache)
        self.assertIn('OFFLINE', input_cache)

    def test_url_cache_offline_hit_and_missing_input(self):
        url = 'https://example.invalid/pinned.tar.gz'
        with tempfile.TemporaryDirectory() as cache:
            path = Path(cache) / hashlib.sha256(url.encode()).hexdigest()
            path.write_bytes(b'pinned')
            with patch.dict(os.environ, {'DOWNLOAD_CACHE': cache, 'OFFLINE': '1'}):
                self.assertEqual(input_cache.download(url), b'pinned')
                with self.assertRaisesRegex(SystemExit, 'offline input missing'):
                    input_cache.download(url + '.missing')

    def test_downloaded_cache_files_are_host_readable(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'source.tar.gz'
            source.write_bytes(b'pinned')
            cache = Path(temporary) / 'cache'
            with patch.dict(os.environ, {'DOWNLOAD_CACHE': cache.as_posix(), 'OFFLINE': '0'}):
                self.assertEqual(input_cache.download(source.as_uri()), b'pinned')
            path = cache / hashlib.sha256(source.as_uri().encode()).hexdigest()
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)

    def test_offline_wrapper_disables_implicit_docker_pull(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / 'repo'
            (repo / 'scripts').mkdir(parents=True)
            (repo / 'out').mkdir()
            shutil.copy(ROOT / 'scripts/build-debs.sh', repo / 'scripts/build-debs.sh')
            source = root / 'source'
            source.mkdir()
            subprocess.check_call(['git', '-C', source.as_posix(), 'init', '-q'])
            subprocess.check_call(['git', '-C', source.as_posix(), 'config', 'user.email', 'test@example.invalid'])
            subprocess.check_call(['git', '-C', source.as_posix(), 'config', 'user.name', 'Test'])
            (source / 'tracked').write_text('source\n')
            subprocess.check_call(['git', '-C', source.as_posix(), 'add', 'tracked'])
            subprocess.check_call(['git', '-C', source.as_posix(), 'commit', '-qm', 'source'])
            sha = subprocess.check_output(['git', '-C', source.as_posix(), 'rev-parse', 'HEAD'], text=True).strip()
            fakebin = root / 'bin'
            fakebin.mkdir()
            docker_log = root / 'docker.log'
            docker = fakebin / 'docker'
            docker.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$DOCKER_LOG"\n')
            docker.chmod(0o755)
            env = os.environ.copy()
            env.update({'OFFLINE': '1', 'COSMOS_DIR': source.as_posix(),
                        'CACHE_DIR': (root / 'cache').as_posix(),
                        'BUILDER_IMAGE': 'missing-image', 'DOCKER_LOG': docker_log.as_posix(),
                        'PATH': fakebin.as_posix() + os.pathsep + env['PATH']})
            subprocess.check_call(['sh', (repo / 'scripts/build-debs.sh').as_posix(), sha], env=env)
            commands = docker_log.read_text().splitlines()
            self.assertEqual(len(commands), 2)
            for command in commands:
                self.assertIn('--pull never', command)

    def test_cached_git_checkout_is_reset_and_missing_pin_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'source'
            source.mkdir()
            subprocess.check_call(['git', '-C', source.as_posix(), 'init', '-q'])
            subprocess.check_call(['git', '-C', source.as_posix(), 'config', 'user.email', 'test@example.invalid'])
            subprocess.check_call(['git', '-C', source.as_posix(), 'config', 'user.name', 'Test'])
            (source / 'tracked').write_text('clean\n')
            subprocess.check_call(['git', '-C', source.as_posix(), 'add', 'tracked'])
            subprocess.check_call(['git', '-C', source.as_posix(), 'commit', '-qm', 'source'])
            sha = subprocess.check_output(['git', '-C', source.as_posix(), 'rev-parse', 'HEAD'], text=True).strip()
            dest = Path(temporary) / 'dest'
            with patch.dict(os.environ, {'OFFLINE': '0'}):
                fetch_cosmos_pins.checkout_git(source.as_posix(), sha, dest.as_posix(), 'fixture')
                (dest / 'tracked').write_text('dirty\n')
                (dest / 'untracked').write_text('dirty\n')
                fetch_cosmos_pins.checkout_git(source.as_posix(), sha, dest.as_posix(), 'fixture')
            self.assertEqual((dest / 'tracked').read_text(), 'clean\n')
            self.assertFalse((dest / 'untracked').exists())
            with patch.dict(os.environ, {'OFFLINE': '1'}):
                with self.assertRaisesRegex(SystemExit, 'offline source missing'):
                    fetch_cosmos_pins.checkout_git(source.as_posix(), '0' * 40, dest.as_posix(), 'fixture')

    def test_actions_restores_before_build_and_saves_only_success(self):
        workflow = read('.github/workflows/apt-trixie-arm64.yml')
        restore = workflow.index('actions/cache/restore@v4')
        build = workflow.index('name: Build packages and stage channel')
        save = workflow.index('actions/cache/save@v4')
        self.assertLess(restore, build)
        self.assertLess(build, save)
        self.assertIn("if: success() && steps.source.outputs.build == 'true'", workflow)
        self.assertIn('github.run_attempt', workflow)
        self.assertIn('continue-on-error: true', workflow)
        self.assertIn('chown -R', workflow)
        for cache in ('ccache', 'sccache', 'downloads', 'cargo/registry'):
            self.assertIn(cache, workflow)


if __name__ == '__main__':
    unittest.main()
