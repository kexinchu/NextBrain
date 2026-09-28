"""Explicit admission of externally reviewed ideas without fabricating scout/challenger rounds."""
from __future__ import annotations

import json
from pathlib import Path

from .contracts import validate_contract
from .io import atomic_write, exclusive_lock, sha256_bytes, sha256_file, utc_stamp, write_json
from .journal import UserMessageJournal
from .transaction import RoundTransaction
from .workflow import WorkflowError, WorkflowState


def admit_external_idea(root: Path, source: Path, digest: str, *, actor: str,
                        reason: str, provenance: dict) -> dict:
    """Import an explicitly approved idea into an unused workspace; story approval stays separate.

    This is an admission transaction, not an agent round. Its ID and receipt are allocated
    by the engine. No host completion, experiment evidence or scientific freeze is fabricated.
    """
    if not actor.strip() or not reason.strip():
        raise WorkflowError('external admission requires an actor and reason')
    content = source.read_text(encoding='utf-8')
    if sha256_bytes(content.encode()) != digest:
        raise WorkflowError('external idea digest differs from the reviewed document')
    with exclusive_lock(root / '.autoresearch' / 'admission.lock'):
        workflow = WorkflowState(root)
        state = workflow.load()
        if state['pending_round'] or any(state[key]['status'] != 'idle'
                                         for key in ('story', 'implementation', 'experiment')):
            raise WorkflowError('external admission requires an unused, idle engine workspace')
        receipt_path = root / '.autoresearch' / 'admissions' / f'{digest}.json'
        if state['idea']['status'] != 'idle':
            if (state['idea'].get('external_digest') == digest and receipt_path.is_file()
                    and sha256_file(root / 'story.md') == digest):
                return json.loads(receipt_path.read_text())
            raise WorkflowError('cannot replace an existing idea workflow')
        existing = root / 'story.md'
        if existing.exists() and sha256_file(existing) != digest:
            raise WorkflowError('existing story.md differs from the approved import')
        transaction = RoundTransaction(root, f'admission-{digest}', ('story.md',))
        if not transaction.directory.exists():
            transaction.create()
        staged = transaction.workspace / 'story.md'
        atomic_write(staged, content)
        contract = validate_contract(staged, stage='idea-story')
        if not contract.metadata.get('selected_candidate'):
            raise WorkflowError('external idea must select one candidate')
        message = UserMessageJournal(root).add(
            'APPROVE external idea ' + digest + '\nActor: ' + actor + '\nReason: ' + reason
            + '\nProvenance: ' + json.dumps(provenance, sort_keys=True), source='external-admission')
        transaction.backup_main(('story.md',))
        transaction.promote(('story.md',))
        receipt = {'kind': 'external-human-admission', 'digest': digest, 'actor': actor,
                   'reason': reason, 'provenance': provenance, 'message_file': message.name,
                   'created_at': utc_stamp(), 'artifacts': ['story.md']}
        write_json(receipt_path, receipt)
        state['idea'].update(status='satisfied', origin='external-human-admission',
                             external_digest=digest, admission_receipt=str(receipt_path))
        workflow.save(state)
        return receipt
