"""Read-only pilot admission. Upstream recommendations never become human GO decisions."""
from pathlib import Path

import yaml

from autoresearch.io import sha256_file


def inspect_go(plans: Path):
    files = sorted(plans.expanduser().resolve(strict=True).glob('*.md'))
    eligible, reviewed = [], []
    for path in files:
        text = path.read_text()
        metadata = {}
        if text.startswith('---\n'):
            parts = text.split('---', 2)
            if len(parts) == 3:
                metadata = yaml.safe_load(parts[1]) or {}
        if not isinstance(metadata, dict):
            metadata = {}
        # A bare GO token in prose/table is not a decision receipt. Require attribution.
        approved = (metadata.get('decision') == 'GO' and isinstance(metadata.get('approval'), dict)
                    and metadata['approval'].get('actor') and metadata['approval'].get('message'))
        record = {'path': str(path), 'sha256': sha256_file(path), 'idea_id': metadata.get('idea_id'),
                  'decision': metadata.get('decision'), 'explicit_go': bool(approved)}
        reviewed.append(record)
        if approved and metadata.get('idea_id'):
            eligible.append(record)
    return {'status': 'PLANNING_ONLY' if eligible else 'HUMAN_GATE_1_REQUIRED',
            'eligible': eligible, 'reviewed': reviewed, 'will_execute': False,
            'reason': 'Only an explicitly attributed GO decision admits a real pilot; pursue/ranking is insufficient.'}
