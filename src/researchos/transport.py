"""Local and SSH transports for the same fixed worker protocol."""
from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

from .ssh import ALIAS, configuration


class TransportError(RuntimeError):
    pass


class LocalTransport:
    def __init__(self, base: Path, worker: Path):
        self.base, self.worker = base.resolve(), worker

    def call(self, payload):
        return invoke([sys.executable, str(self.worker)], {**payload, 'local_base': str(self.base)})


class SSHTransport:
    def __init__(self, alias: str, config: Path, worker: Path):
        if not ALIAS.fullmatch(alias):
            raise ValueError('invalid SSH alias')
        aliases, hazards = configuration(config)
        if alias not in aliases or hazards:
            raise ValueError('executor requires a literal alias and static SSH config without Match exec')
        self.alias, self.config, self.worker = alias, config, worker

    def call(self, payload):
        # SSH invokes a login shell for its command. Quote every remote argument; no user shell
        # snippets are interpolated. The fixed controller reads structured input on stdin.
        command = shlex.join(['python3', '-c', self.worker.read_text()])
        argv = ['ssh', '-F', str(self.config), '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
                '-o', 'StrictHostKeyChecking=yes', '-o', 'PermitLocalCommand=no',
                '-o', 'ProxyCommand=none', '-o', 'ProxyJump=none', '-o', 'ControlMaster=no',
                '-o', 'ControlPath=none', '-o', 'ClearAllForwardings=yes', '-o', 'ForwardAgent=no',
                '-o', 'ForwardX11=no', '-o', 'UpdateHostKeys=no', '-o', 'AddKeysToAgent=no',
                '-o', 'RemoteCommand=none', '-o', 'RequestTTY=no', '-o', 'Tunnel=no',
                self.alias, command]
        return invoke(argv, payload)


def invoke(argv, payload):
    try:
        completed = subprocess.run(argv, input=json.dumps(payload), capture_output=True,
                                   text=True, timeout=45)
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise TransportError(str(exc)) from exc
    if completed.returncode:
        raise TransportError(completed.stderr[-8000:] or 'executor control connection failed')
    try:
        result = json.loads(completed.stdout)
    except ValueError as exc:
        raise TransportError('executor did not return valid JSON') from exc
    if not isinstance(result, dict):
        raise TransportError('invalid executor response')
    return result
