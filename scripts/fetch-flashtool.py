#!/usr/bin/env python3
"""Fetch Katapult using flashtool's recipe and versioned include in Cosmos."""
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys

parser = runpy.run_path(os.path.join(os.path.dirname(__file__), 'fetch-cosmos-pins.py'))
root = sys.argv[1]
recipe = Path(parser['recipe_files'](root, 'flashtool')[-1])
version = parser['recipe_version'](root, 'flashtool')
visited = set()


def read_recipe(path):
    path = path.resolve()
    if path in visited:
        raise RuntimeError(f'Recursive recipe include: {path}')
    visited.add(path)
    text = path.read_text().replace('\\\n', '')
    for include in re.findall(r'^require\s+(\S+)', text, re.M):
        text += '\n' + read_recipe(path.parent / include.replace('${PV}', version))
    return text


text = read_recipe(recipe)
uri = re.search(r'(?:git|gitsm)://([^;\s\"]+)', text)
rev = re.search(r'SRCREV\s*=\s*"([0-9a-fA-F]+)"', text)
if not uri or not rev:
    raise SystemExit(f'Missing Katapult git pin in {recipe}')
dest = '/upstream/flashtool'
print(f'pin flashtool: {version} https://{uri.group(1)} @ {rev.group(1)}', flush=True)
parser['checkout_git']('https://' + uri.group(1), rev.group(1), dest, 'flashtool')
for patch in re.findall(r'file://([^;\s\"]+\.patch)', text):
    path = (recipe.parent / 'files' / patch).resolve()
    subprocess.check_call(['patch', '-d', dest, '-p1', '-i', str(path)])
with open('/tmp/package-versions', 'a') as handle:
    handle.write(f'flashtool {version}\n')
