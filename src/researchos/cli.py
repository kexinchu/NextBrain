from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

import yaml

from .service import ResearchOS
from .ssh import import_config, probe


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog='researchos')
    root.add_argument('--home', type=Path,
                      default=Path(os.environ.get('RESEARCHOS_HOME', '~/.local/share/researchos')))
    commands = root.add_subparsers(dest='command', required=True)
    scan = commands.add_parser('scan')
    scan.add_argument('--plans', type=Path, required=True)
    scan.add_argument('--source-root', type=Path,
                      help='allowed root for linked source documents (defaults to plans)')
    commands.add_parser('inbox')
    commands.add_parser('status')
    decide = commands.add_parser('decide')
    decide.add_argument('idea')
    decide.add_argument('decision', choices=['GO', 'HOLD', 'DROP', 'NEEDS_WORK'])
    decide.add_argument('--by', required=True)
    decide.add_argument('--reason', required=True)
    for name in ('hypothesis', 'claim', 'experiment', 'run', 'finding'):
        command = commands.add_parser(name)
        actions = command.add_subparsers(dest='action', required=True)
        add = actions.add_parser('add')
        add.add_argument('--project', required=True)
        add.add_argument('--file', type=Path, required=True)
        listing = actions.add_parser('list')
        listing.add_argument('--project', required=True)
        if name == 'experiment':
            ready = actions.add_parser('ready')
            ready.add_argument('experiment')
    contract = commands.add_parser('contract')
    actions = contract.add_subparsers(dest='action', required=True)
    for name in ('check', 'approve'):
        action = actions.add_parser(name)
        action.add_argument('project')
        if name == 'approve':
            action.add_argument('--digest', required=True)
            action.add_argument('--by', required=True)
            action.add_argument('--reason', required=True)
    handoff = commands.add_parser('handoff')
    handoff.add_argument('project')
    handoff.add_argument('--story', type=Path, required=True)
    handoff.add_argument('--digest', required=True)
    handoff.add_argument('--by', required=True)
    handoff.add_argument('--reason', required=True)
    context = commands.add_parser('context')
    context.add_argument('project')
    artifact = commands.add_parser('artifact')
    artifact.add_argument('--run', required=True)
    artifact.add_argument('--file', type=Path, required=True)
    ssh = commands.add_parser('ssh')
    actions = ssh.add_subparsers(dest='action', required=True)
    importing = actions.add_parser('import')
    importing.add_argument('--config', type=Path, default=Path('~/.ssh/config'))
    probing = actions.add_parser('probe')
    probing.add_argument('alias')
    actions.add_parser('list')
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        app = ResearchOS(args.home)
        if args.command == 'scan':
            result = app.scan(args.plans, args.source_root)
        elif args.command == 'inbox':
            result = app.inbox()
        elif args.command == 'status':
            result = app.status()
        elif args.command == 'decide':
            result = app.decide(args.idea, args.decision, args.by, args.reason)
        elif args.command == 'handoff':
            result = app.handoff(args.project, args.story, args.digest, args.by, args.reason)
        elif args.command == 'context':
            result = app.context(args.project)
        elif args.command == 'artifact':
            result = app.artifact(args.run, args.file)
        elif args.command == 'contract':
            if args.action == 'approve':
                result = app.approve_contract(args.project, args.digest, args.by, args.reason)
            else:
                data, digest = app.contract(args.project)
                result = {'contract': data, 'digest': digest}
        elif args.command == 'ssh':
            if args.action == 'import':
                result = import_config(app.store, args.config)
            elif args.action == 'probe':
                result = probe(app.store, args.alias)
            else:
                result = app.store.list('machines')
        elif args.action == 'ready':
            result = app.readiness(args.experiment)
        elif args.action == 'add':
            data = yaml.safe_load(args.file.read_text())
            result = app.add(args.command, args.project, data)
        else:
            table = {'hypothesis': 'hypotheses', 'claim': 'claims', 'experiment': 'experiments',
                     'run': 'runs', 'finding': 'findings'}[args.command]
            result = app.store.list(table, args.project)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        if args.command == 'ssh' and args.action == 'probe' and result['data']['status'] != 'OK':
            return 1
        return 0
    except (ValueError, RuntimeError, OSError, sqlite3.Error, yaml.YAMLError) as exc:
        print(f'researchos: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
