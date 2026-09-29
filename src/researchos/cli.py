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
        if name == 'run':
            create = actions.add_parser('create')
            create.add_argument('experiment')
            create.add_argument('--machine')
            for operation in ('dispatch', 'status', 'recover', 'retry', 'cancel'):
                op = actions.add_parser(operation)
                op.add_argument('run_id')
        if name == 'experiment':
            freeze = actions.add_parser('freeze')
            freeze.add_argument('experiment')
            freeze.add_argument('--repo', type=Path, required=True)
    next_command = commands.add_parser('next')
    next_command.add_argument('project')
    research = commands.add_parser('research')
    ra = research.add_subparsers(dest='action', required=True)
    for operation in ('question', 'edge', 'debt', 'branch', 'maturity'):
        op = ra.add_parser(operation)
        op.add_argument('project')
        if operation != 'maturity':
            op.add_argument('--file', type=Path, required=True)
    for operation in ('trajectory', 'journal'):
        op = commands.add_parser(operation)
        op.add_argument('project')
    evaluate = commands.add_parser('evaluate-planner')
    evaluate.add_argument('--cases', type=Path, required=True)
    pilot = commands.add_parser('pilot-check')
    pilot.add_argument('--plans', type=Path, required=True)
    advance = commands.add_parser('advance')
    advance.add_argument('project')
    advance.add_argument('--max-runs', type=int, default=1)
    advance.add_argument('--max-wall-time', default='1h')
    advance.add_argument('--resume')
    uncertainty = commands.add_parser('uncertainty')
    ua = uncertainty.add_subparsers(dest='action', required=True)
    for operation in ('add', 'list'):
        op = ua.add_parser(operation)
        op.add_argument('project')
        if operation == 'add':
            op.add_argument('--file', type=Path, required=True)
    planner = commands.add_parser('planner')
    pa = planner.add_subparsers(dest='action', required=True)
    for operation in ('import', 'context', 'decisions'):
        op = pa.add_parser(operation)
        op.add_argument('project')
        if operation == 'import':
            op.add_argument('--file', type=Path, required=True)
    gate = commands.add_parser('gate')
    ga = gate.add_subparsers(dest='action', required=True)
    review = ga.add_parser('review')
    review.add_argument('project')
    approve = ga.add_parser('approve')
    approve.add_argument('gate_id')
    approve.add_argument('--digest', required=True)
    approve.add_argument('--decision', required=True, choices=['CONTINUE','STOP','PIVOT','FREEZE_STORY', 'CONTINUE_EXPLORATION',
               'FOCUS_MECHANISM', 'REPLICATE', 'EXPAND_EVALUATION', 'STOP_PROJECT', 'REQUEST_SCOPE_CHANGE'])
    approve.add_argument('--message-file', type=Path, required=True)
    approve.add_argument('--by', required=True)
    envelope = commands.add_parser('envelope')
    actions = envelope.add_subparsers(dest='action', required=True)
    for operation in ('check', 'approve'):
        op = actions.add_parser(operation)
        op.add_argument('project')
        if operation == 'approve':
            op.add_argument('--digest', required=True)
            op.add_argument('--message-file', type=Path, required=True)
            op.add_argument('--by', required=True)
    scope = commands.add_parser('scope')
    scope_actions = scope.add_subparsers(dest='action', required=True)
    scope_request = scope_actions.add_parser('request')
    scope_request.add_argument('project')
    scope_request.add_argument('--file', type=Path, required=True)
    scope_approve = scope_actions.add_parser('approve')
    scope_approve.add_argument('request_id')
    scope_approve.add_argument('--digest', required=True)
    scope_approve.add_argument('--message-file', type=Path, required=True)
    scope_approve.add_argument('--by', required=True)
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
        if args.command == 'research':
            from .intelligence import set_question, add_edge, add_debt, branch, claim_maturity
            if args.action == 'maturity':
                result = claim_maturity(app, args.project)
            else:
                operation = {'question': set_question, 'edge': add_edge, 'debt': add_debt, 'branch': branch}[args.action]
                result = operation(app, args.project, yaml.safe_load(args.file.read_text()))
        elif args.command in {'trajectory', 'journal'}:
            from .intelligence import trajectory, journal
            print((trajectory if args.command == 'trajectory' else journal)(app, args.project))
            return 0
        elif args.command == 'evaluate-planner':
            from .reasoning_eval import evaluate_cases
            result = evaluate_cases(args.cases)
            print(json.dumps(result, indent=2))
            return 0 if result['passed'] else 1
        elif args.command == 'pilot-check':
            from .pilot import inspect_go
            result = inspect_go(args.plans)
        elif args.command == 'advance':
            from .advance import advance
            result = advance(app, args.project, args.max_runs, args.max_wall_time, args.resume)
        elif args.command == 'uncertainty':
            from .research_state import add_uncertainty
            result = (add_uncertainty(app, args.project, yaml.safe_load(args.file.read_text()))
                      if args.action == 'add' else app.store.list('uncertainties', args.project))
        elif args.command == 'planner':
            from .planner import import_proposals
            from .research_state import build_context
            if args.action == 'import':
                result = import_proposals(app, args.project, yaml.safe_load(args.file.read_text()))
            elif args.action == 'context':
                result = build_context(app, args.project)
            else:
                result = app.store.list('planner_decisions', args.project)
        elif args.command == 'gate':
            from .controller import approve_gate, gate_summary
            result = (gate_summary(app, args.project, 'Explicit human evidence review')
                      if args.action == 'review' else approve_gate(
                          app, args.gate_id, args.digest, args.decision, args.message_file, args.by))
        elif args.command == 'envelope':
            from .policy import Policy
            policy = Policy(app)
            if args.action == 'check':
                data, digest = policy.envelope_draft(args.project)
                result = {'envelope': data, 'digest': digest}
            else:
                result = policy.approve_envelope(args.project, args.digest, args.message_file, args.by)
        elif args.command == 'scope':
            from .policy import Policy
            if args.action == 'request':
                result = Policy(app).scope_request(args.project, yaml.safe_load(args.file.read_text()))
            else:
                result = Policy(app).approve_scope(args.request_id, args.digest, args.message_file, args.by)
        elif args.command == 'next':
            from .next_experiment import prepare_next
            result = prepare_next(app, args.project)
        elif args.command == 'run' and args.action not in {'add', 'list'}:
            from .execution import Runs
            runs = Runs(app)
            if args.action == 'create':
                result = runs.create(args.experiment, args.machine)
            else:
                result = getattr(runs, args.action)(args.run_id)
        elif args.command == 'experiment' and args.action == 'freeze':
            from .freeze import freeze_experiment
            result = freeze_experiment(app, args.experiment, args.repo)
        elif args.command == 'scan':
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
