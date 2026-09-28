"""Read plans without changing the upstream vault or interpreting recommendations as approval."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from autoresearch.io import sha256_bytes

ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")
HEADING = re.compile(r"^##\s+(?:\d+\.\s*)?`([A-Za-z0-9_.-]+)`\s+(.+)$", re.M)


def identifier(value: str) -> str:
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError(f"invalid identifier: {value!r}")
    return value


def scan_plans(directory: Path, source_root: Path | None = None) -> list[dict]:
    directory = directory.expanduser().resolve(strict=True)
    source_root = (source_root or directory).expanduser().resolve(strict=True)
    directory.relative_to(source_root)
    records = []
    for path in sorted(directory.rglob('*.md')):
        path.resolve().relative_to(source_root)
        text = path.read_text(encoding='utf-8')
        front = re.match(r'^---\n(.*?)\n---\n', text, re.S)
        items = []
        if front:
            meta = yaml.safe_load(front[1])
            if isinstance(meta, dict) and 'idea_id' in meta:
                items = [(identifier(meta['idea_id']), meta.get('title'), text)]
        if not items:
            headings = list(HEADING.finditer(text))
            for index, match in enumerate(headings):
                end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
                items.append((identifier(match[1]), match[2], text[match.start():end]))
        # Plain Markdown is supported with a stable relative-path-derived ID. For durable
        # identity across renames, authors should provide idea_id frontmatter.
        if not items:
            title = re.search(r'^#\s+(.+)$', text, re.M)
            if not title:
                continue
            relative = path.relative_to(directory).as_posix()
            items = [('I-' + sha256_bytes(relative.encode())[:16], title[1], text)]
        for idea_id, title, excerpt in items:
            if not isinstance(title, str) or not title.strip():
                raise ValueError(f'{path}: candidate {idea_id} needs a title')
            # Decision packets often keep the full-plan links in an overview table.
            overview = '\n'.join(line for line in text.splitlines()
                                 if line.lstrip().startswith('|') and f'`{idea_id}`' in line)
            excerpt = excerpt + ('\n\n' + overview if overview else '')
            links, unresolved = {}, []
            for target in re.findall(r'\[\[([^\]|]+)(?:\|[^\]]*)?\]\]', excerpt):
                target = target.split('#', 1)[0]
                if not target:
                    continue
                linked = (path.parent / target).with_suffix('.md').resolve()
                try:
                    linked.relative_to(source_root)
                except ValueError:
                    unresolved.append(target)
                    continue
                if linked.is_file():
                    links[str(linked)] = linked.read_text(encoding='utf-8')
                else:
                    unresolved.append(target)
            snapshot = {'source_path': str(path), 'excerpt': excerpt,
                        'linked_documents': links, 'unresolved_links': sorted(set(unresolved))}
            records.append({'id': idea_id, 'title': title.strip(), 'snapshot': snapshot})
    ids = [r['id'] for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate idea IDs in scan; resolve before importing')
    return records
