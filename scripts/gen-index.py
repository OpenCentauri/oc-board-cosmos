#!/usr/bin/env python3
"""Generate nginx-style archive indexes.

Adapted from pdscomp/kipware scripts/gen-index.py, blob
4722539ce8d3708c7e15a7209de8d74a24377878.
Preserves its preformatted layout, date/size columns and name truncation.
Changes: discover all archive directories, encode URLs, skip hidden files
and symlinks, and regenerate indexes on each deployment.
"""
import argparse
import datetime
from html import escape
from pathlib import Path
from urllib.parse import quote

MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
NAME_WIDTH = 51


def fmt_date(ts):
    d = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
    return f'{d.day:02d}-{MONTHS[d.month - 1]}-{d.year} {d.hour:02d}:{d.minute:02d}'


def fmt_size(path):
    return '-' if path.is_dir() else str(path.stat().st_size)


def entry_line(href, name, date_str, size_str='-'):
    visible = name[:NAME_WIDTH - 3] + '..>' if len(name) > NAME_WIDTH else name
    padding = ' ' * (NAME_WIDTH - len(visible))
    size_col = size_str.rjust(20)
    return (f'<a href="{escape(href, quote=True)}">'
            f'{escape(visible)}</a>{padding}{date_str}{size_col}')


def build_page(title, parent_href, entry_lines):
    lines = ['<!doctype html>', '<html lang="en">',
             f'<head><meta charset="utf-8"><title>Index of {escape(title)}</title></head>',
             '<body>', f'<h1>Index of {escape(title)}</h1><hr><pre>']
    if parent_href is not None:
        lines.append(f'<a href="{escape(parent_href, quote=True)}">../</a>')
    lines.extend(entry_lines)
    lines += ['</pre><hr></body>', '</html>', '']
    return '\n'.join(lines)


def generate(root):
    if root.is_symlink() or not root.is_dir():
        raise SystemExit(f'Not an archive directory: {root}')
    root = root.resolve()
    def visit(directory):
        children = sorted((p for p in directory.iterdir()
                           if not p.name.startswith('.') and p.name != 'index.html'
                           and not p.is_symlink() and (p.is_file() or p.is_dir())),
                          key=lambda p: (not p.is_dir(), p.name.lower()))
        rel = directory.relative_to(root).as_posix()
        title = '/oc-board-cosmos/' + ('' if rel == '.' else rel + '/')
        lines = [entry_line(quote(c.name, safe='') + ('/' if c.is_dir() else ''),
                            c.name + ('/' if c.is_dir() else ''),
                            fmt_date(c.stat().st_mtime), fmt_size(c)) for c in children]
        (directory / 'index.html').write_text(
            build_page(title, None if directory == root else '../', lines), encoding='utf-8')
        for child in children:
            if child.is_dir():
                visit(child)
    visit(root)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    generate(parser.parse_args().archive)
