"""Bounded coordinator; all actual execution remains in the V0.1 Runs primitive."""
from __future__ import annotations

import json
import time
from pathlib import Path

from autoresearch.io import exclusive_lock, utc_stamp

from .controller import after_run, gate_summary
from .execution import Runs, TERMINAL
from .freeze import freeze_experiment
from .planner import assert_fresh, effective_spec, plan
from .research_state import enable
from .service import uid
from .store import encoded
from .transport import LocalTransport, SSHTransport, TransportError


def seconds(value):
    if isinstance(value, str):
        units = {'s': 1, 'm': 60, 'h': 3600}
        value = float(value[:-1]) * units[value[-1]] if value[-1:] in units else float(value)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 86400:
        raise ValueError('max_wall_time must be positive and at most 24h')
    return float(value)


def advance(app, project, max_runs=1, max_wall_time=3600, resume=None, reasoner=None, runs=None):
    if isinstance(max_runs, bool) or not isinstance(max_runs, int) or not 1 <= max_runs <= 10:
        raise ValueError('max_runs must be an integer between 1 and 10')
    wall = seconds(max_wall_time)
    enable(app, project)
    with exclusive_lock(app.root / 'advance-locks' / (project + '.lock'), timeout=1):
        return _advance(app, project, max_runs, wall, resume, reasoner, runs)


def _advance(app, project, max_runs, wall, resume, reasoner, runs):
    if resume:
        row = app.same_project('advances', resume, project)
        if row['state'] not in {'RUNNING', 'RECOVERY_REQUIRED', 'INTERRUPTED'}:
            raise ValueError('advance is already stopped; start a new explicitly bounded advance')
        info = json.loads(row['data'])
        loop_id = resume
    else:
        with app.store.connect() as db:
            active = db.execute("SELECT id FROM advances WHERE project_id=? AND state IN "
                                "('RUNNING','RECOVERY_REQUIRED','INTERRUPTED')", (project,)).fetchone()
            orphan = db.execute("SELECT id FROM executions WHERE project_id=? AND state IN "
                                "('CREATED','PREPARING','DISPATCHED','RUNNING','COLLECTING','LOST')",
                                (project,)).fetchone()
        if active or orphan:
            raise ValueError('resume/recover existing work before starting another advance')
        loop_id = uid('ADVANCE')
        info = {'max_runs': max_runs, 'deadline': time.time() + wall, 'max_wall_time': wall,
                'run_ids': [], 'planner_decisions': [], 'controllers': [], 'stop_reason': None}
        with app.store.connect() as db:
            db.execute('INSERT INTO advances VALUES (?,?,?,?,?)',
                       (loop_id, project, encoded(info), 'RUNNING', utc_stamp()))
    deadline = info['deadline']

    def transport(run, worker):
        if run['machine_alias'] == 'local':
            target = LocalTransport(app.root / 'executor', worker)
        else:
            machine = app.store.get('machines', run['machine_alias'])
            target = SSHTransport(run['machine_alias'], Path(machine['config_path']), worker)
        target.deadline = deadline
        return target

    executor = runs or Runs(app, transport)

    def save(state='RUNNING', reason=None):
        info['stop_reason'] = reason
        with app.store.connect() as db:
            db.execute('UPDATE advances SET data=?,state=? WHERE id=?', (encoded(info), state, loop_id))
        return {'id': loop_id, 'project_id': project, 'state': state, **info}

    def replan():
        decision = plan(app, project, reasoner)
        info['planner_decisions'].append(decision['id'])
        save()
        return decision

    try:
        while True:
            # Resume only the last linked run. Never create a replacement for uncertain execution.
            with app.store.connect() as db:
                links = db.execute('SELECT run_id FROM advance_runs WHERE advance_id=? ORDER BY rowid',
                                   (loop_id,)).fetchall()
            info['run_ids'] = [r[0] for r in links]
            run_id = next((r for r in info['run_ids'] if r not in info['controllers']), None)
            if run_id:
                state = executor.status(run_id)
                if state['state'] == 'CREATED':
                    frozen = json.loads(app.store.get('experiment_freezes', state['freeze_id'])['data'])
                    if frozen['timeout'] + 1 > deadline - time.time():
                        executor.cancel(run_id)
                        return save('STOPPED', 'MAX_WALL_TIME: reserved run cancelled before dispatch')
                    state = executor.dispatch(run_id)
                while state['state'] not in TERMINAL:
                    if time.time() >= deadline:
                        try:
                            executor.cancel(run_id)
                        except (TransportError, ValueError):
                            pass
                        return save('RECOVERY_REQUIRED', 'MAX_WALL_TIME; cancellation attempted; recover the same run')
                    state = executor.recover(run_id)
                    if state['state'] == 'LOST':
                        return save('RECOVERY_REQUIRED', 'LOST execution; no replacement dispatched')
                    if state['state'] not in TERMINAL:
                        time.sleep(min(.1, max(0, deadline - time.time())))
                control = after_run(app, run_id)
                info['controllers'].append(run_id)
                save()
                # Even at the last-run boundary, create an auditable new plan after the Finding.
                decision = replan()
                if control['action'] in {'STOP_PROJECT', 'ESCALATE_HUMAN'}:
                    return save('STOPPED', control['action'] + ': ' + control['reason'])
                if state['state'] != 'SUCCEEDED':
                    return save('STOPPED', 'OPERATIONAL_FAILURE; explicit recovery/retry or revised proposal required')
            else:
                decision = replan()
            if time.time() >= deadline:
                return save('STOPPED', 'MAX_WALL_TIME')
            if len(info['run_ids']) >= info['max_runs']:
                return save('STOPPED', 'MAX_RUNS')
            with app.store.connect() as db:
                pending = db.execute('SELECT id FROM maturity_gates WHERE project_id=? AND action IS NULL',
                                     (project,)).fetchone()
            if pending:
                return save('STOPPED', 'HUMAN_GATE_2: ' + pending[0])
            if not decision['selected']:
                reasons = [b for s in decision['selection_scores'] for b in s['blockers']]
                reason = '; '.join(reasons) or 'No useful in-scope candidate supplied'
                context = decision['context']
                scope_change = not decision['scope_check'] or context['project_state'] == 'SCOPE_CHANGE_REQUESTED'
                exhausted = bool(context['hypotheses']) and all(
                    h['state'] in {'FALSIFIED', 'BLOCKED'} for h in context['hypotheses'])
                project_stop = (exhausted or context['project_state'] == 'STOPPED'
                                or any('budget exhausted' in r for r in reasons))
                if scope_change or project_stop:
                    action = 'ESCALATE_HUMAN' if scope_change else 'STOP_PROJECT'
                    gate = gate_summary(app, project, reason, 'PIVOT' if scope_change else 'STOP')
                    control = {'id': uid('CONTROL'), 'project_id': project, 'action': action,
                               'reason': reason, 'gate_id': gate['id'], 'recommendation_only': True}
                    with app.store.connect() as db:
                        db.execute('INSERT INTO controller_decisions VALUES (?,?,?,?)',
                                   (control['id'], project, encoded(control), utc_stamp()))
                    return save('STOPPED', action + ': ' + reason + '; gate=' + gate['id'])
                return save('STOPPED', 'AWAITING_IN_SCOPE_PROPOSALS: ' + reason)
            selected = decision['selected']['candidate']
            # Admit only a run that fits the remaining loop deadline, including control headroom.
            overhead = 2 if decision['selected']['machine']['alias'] == 'local' else 90
            if selected['spec']['timeout'] + overhead > deadline - time.time():
                return save('STOPPED', 'MAX_WALL_TIME: next run cannot fit remaining allowance')
            if selected['spec']['resource_requirement'].get('gpu_required'):
                from .ssh import probe
                alias = decision['selected']['machine']['alias']
                if alias != 'local':
                    probe(app.store, alias)
                    checked = replan()
                    if not checked['selected'] or checked['selected_experiment'] != selected['spec']['id']:
                        return save('STOPPED', 'GPU_PREFLIGHT: machine or policy changed; review fresh plan')
                    decision = checked
            assert_fresh(app, decision)
            spec = effective_spec(selected)
            with app.store.connect() as db:
                exists = db.execute('SELECT 1 FROM experiments WHERE id=?', (spec['id'],)).fetchone()
            if not exists:
                app.add('experiment', project, spec)
            freeze_experiment(app, spec['id'], Path(selected['repo']))
            # Registration changes durable state; revalidate the actual choice against it.
            admitted = replan()
            if not admitted['selected'] or admitted['selected_experiment'] != spec['id']:
                return save('STOPPED', 'REPLAN_CHANGED_SELECTION; no dispatch')
            assert_fresh(app, admitted)
            if spec['timeout'] + overhead > deadline - time.time():
                return save('STOPPED', 'MAX_WALL_TIME: preparation used the remaining allowance')
            run = executor.create(spec['id'], admitted['selected']['machine']['alias'])
            with app.store.connect() as db:
                db.execute('INSERT INTO advance_runs VALUES (?,?,?)', (loop_id, run['id'], admitted['id']))
            info['run_ids'].append(run['id'])
            save()
            # Dispatch on the next iteration, after the coordinator link is durable.
    except KeyboardInterrupt:
        save('INTERRUPTED', 'Coordinator interrupted; resume the same advance')
        raise
    except (ValueError, OSError, TransportError) as exc:
        return save('RECOVERY_REQUIRED' if info['run_ids'] else 'STOPPED', str(exc))
