#!/usr/bin/env python3
"""Reuse the Cosmos recipe parser to fetch the current mcu-flasher pin."""
import os
import runpy
import sys

parser = runpy.run_path(os.path.join(os.path.dirname(__file__), "fetch-cosmos-pins.py"))
root = sys.argv[1]
parser["fetch_git"](root, "mcu-flasher")
version = parser["recipe_version"](root, "mcu-flasher")
with open("/tmp/package-versions", "a") as handle:
    handle.write(f"mcu-flasher {version}\n")
