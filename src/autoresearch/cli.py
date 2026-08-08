from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agent import CommandAgent, OpenAIAgent
from .doctor import Doctor
from .e2e import CLIENTS, E2ERegistry
from .evaluation import CapabilityEvaluator
from .freeze import FreezeGuard
from .host import HostRoundManager
from .installer import ConversationSkillInstaller
from .journal import UserMessageJournal
from .orchestrator import AutoResearch
from .requirements import RequirementSummary
from .skills import list_skills, load_skill
from .topic import TopicDocument
from .venues import PROFILES, resolve_venue
from .workspace import ResearchWorkspace


def _agent_from_args(args: argparse.Namespace):
    if args.agent_command:
        return CommandAgent(args.agent_command, timeout_seconds=args.timeout)
    if args.openai_model:
        return OpenAIAgent(args.openai_model, reasoning_effort=args.reasoning_effort)
    raise SystemExit("choose an agent backend with --agent-command or --openai-model")


def _print_outcomes(outcomes) -> None:
    if not isinstance(outcomes, list):
        outcomes = [outcomes]
    print(json.dumps([item.as_dict() for item in outcomes], ensure_ascii=False, indent=2))


def _record_run_directive(root: Path, args: argparse.Namespace) -> Path:
    fields = {"skill": args.skill, "openai_model": args.openai_model}
    if args.skill == "idea":
        fields.update(
            topic=args.topic,
            max_rounds=args.max_rounds,
            sample_size=args.sample_size,
        )
    elif args.skill == "story":
        fields.update(idea=args.idea, human_context=args.human_context)
    elif args.skill == "implement":
        fields.update(max_rounds=args.max_rounds, check_command=args.check_command)
    elif args.skill == "experiment":
        fields.update(max_rounds=args.max_rounds, run_command=args.run_command)
    elif args.skill == "write":
        fields.update(
            venue=args.venue,
            section=args.section,
            accepted_corpus=args.accepted_corpus,
        )
    elif args.skill == "review":
        fields.update(venue=args.venue, venue_guide=args.venue_guide)
    lines = ["# AutoResearch run directive", ""]
    lines.extend(f"- {name}: `{value}`" for name, value in fields.items() if value not in (None, ""))
    return UserMessageJournal(root).add("\n".join(lines), source=f"run-{args.skill}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autoresearch")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("init", help="scaffold a research workspace")

    requirements = commands.add_parser("requirements", help="manage the compact requirement view")
    requirement_commands = requirements.add_subparsers(dest="requirements_command", required=True)
    requirement_update = requirement_commands.add_parser("update")
    requirement_update.add_argument("--file", type=Path, required=True)
    requirement_commands.add_parser("status")

    message = commands.add_parser("message", help="record one immutable user message")
    message.add_argument("text", nargs="?")
    message.add_argument("--file", type=Path)
    message.add_argument("--source", default="user")

    skills = commands.add_parser("skills", help="list or inspect installed skills")
    skills.add_argument("action", choices=("list", "show"), default="list", nargs="?")
    skills.add_argument("name", nargs="?")

    venues = commands.add_parser("venues", help="list or inspect research venue profiles")
    venues.add_argument("action", choices=("list", "show"), default="list", nargs="?")
    venues.add_argument("name", nargs="?")

    freeze = commands.add_parser("freeze", help="create or verify content-hash freezes")
    freeze.add_argument("action", choices=("create", "verify"))
    freeze.add_argument("name")
    freeze.add_argument("paths", nargs="*")

    install = commands.add_parser(
        "install-skills", help="install conversation-native skills for GPT, Claude, or Cursor"
    )
    install.add_argument("--target", choices=("gpt", "codex", "claude", "cursor", "all"), required=True)
    install.add_argument("--scope", choices=("project", "user"), default="project")
    install.add_argument("--force", action="store_true")

    client_skills = commands.add_parser(
        "client-skills", help="install, update, inspect, or uninstall conversation skills"
    )
    client_skills.add_argument("action", choices=("install", "update", "status", "uninstall"))
    client_skills.add_argument(
        "--target", choices=("gpt", "codex", "claude", "cursor", "all"), required=True
    )
    client_skills.add_argument("--scope", choices=("project", "user"), default="project")
    client_skills.add_argument("--force", action="store_true")

    doctor = commands.add_parser("doctor", help="validate workspace and client-skill readiness")
    doctor.add_argument("--require-e2e", action="store_true")
    doctor.add_argument("--release", action="store_true")

    e2e = commands.add_parser("e2e", help="record or inspect real client E2E evidence")
    e2e_commands = e2e.add_subparsers(dest="e2e_command", required=True)
    e2e_record = e2e_commands.add_parser("record")
    e2e_record.add_argument("--client", choices=CLIENTS, required=True)
    e2e_record.add_argument("--skill", choices=tuple(skill.name for skill in list_skills()), required=True)
    e2e_record.add_argument("--model", required=True)
    e2e_record.add_argument("--status", choices=("pass", "fail"), required=True)
    e2e_record.add_argument("--evidence", type=Path, required=True)
    e2e_commands.add_parser("status")

    evaluate = commands.add_parser("eval", help="run local capability gates")
    evaluate.add_argument("--require-e2e", action="store_true")
    evaluate.add_argument("--release", action="store_true")

    host = commands.add_parser("host", help="run deterministic rounds using the current chat model")
    host_commands = host.add_subparsers(dest="host_command", required=True)
    host_begin = host_commands.add_parser("begin")
    host_begin.add_argument("--skill", choices=tuple(load.name for load in list_skills()), required=True)
    host_begin.add_argument("--role", required=True)
    host_begin.add_argument("--message-file", required=True)
    host_begin.add_argument("--section")
    host_begin.add_argument("--venue")
    host_begin.add_argument("--max-rounds", type=int, default=8)
    host_begin.add_argument("--sample-size", type=int, default=3)
    host_complete = host_commands.add_parser("complete")
    host_complete.add_argument("round_id")
    host_complete.add_argument(
        "--decision", choices=("continue", "satisfied", "blocked", "report"), required=True
    )
    host_complete.add_argument("--summary", default="")
    host_complete.add_argument("--output-file")
    host_check = host_commands.add_parser("check")
    host_check.add_argument("round_id")
    host_check.add_argument("command_name")
    host_approve = host_commands.add_parser("approve-story")
    host_approve.add_argument("--message-file", required=True)
    host_reset = host_commands.add_parser("reset")
    host_reset.add_argument("--skill", choices=tuple(skill.name for skill in list_skills()), required=True)
    host_reset.add_argument("--message-file", required=True)
    host_commands.add_parser("status")

    run = commands.add_parser("run", help="deprecated standalone adapter mode")
    run.add_argument("skill", choices=("idea", "story", "implement", "experiment", "write", "review"))
    run.add_argument("--agent-command")
    run.add_argument("--openai-model")
    run.add_argument("--reasoning-effort", default="medium")
    run.add_argument("--timeout", type=int, default=1800)
    run.add_argument("--max-rounds", type=int, default=8)
    run.add_argument("--topic", type=Path, help="Markdown file containing the active topic")
    run.add_argument("--sample-size", type=int, default=3)
    run.add_argument("--idea", default="story.md")
    run.add_argument("--human-context", default="")
    run.add_argument("--check-command")
    run.add_argument("--run-command")
    run.add_argument("--venue")
    run.add_argument("--section")
    run.add_argument("--accepted-corpus")
    run.add_argument("--venue-guide")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.workspace.resolve()
    if args.command == "init":
        created = ResearchWorkspace(root).init()
        print(f"Initialized {root}; created {len(created)} files")
        return 0
    if args.command == "message":
        if bool(args.text) == bool(args.file):
            raise SystemExit("provide exactly one of message text or --file")
        text = args.text if args.text else args.file.read_text(encoding="utf-8")
        path = UserMessageJournal(root).add(text, source=args.source)
        print(path)
        return 0
    if args.command == "requirements":
        summary = RequirementSummary(root)
        if args.requirements_command == "update":
            print(summary.update(args.file.read_text(encoding="utf-8")))
        else:
            print(json.dumps(summary.status(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "skills":
        if args.action == "show":
            if not args.name:
                raise SystemExit("skills show requires a skill name")
            skill = load_skill(args.name)
            print(skill.body)
        else:
            for skill in list_skills():
                print(f"{skill.name}\t{skill.description}")
        return 0
    if args.command == "venues":
        if args.action == "show":
            if not args.name:
                raise SystemExit("venues show requires a venue name")
            print(
                json.dumps(
                    resolve_venue(args.name, allow_inactive=True).as_dict(),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(
                json.dumps(
                    [profile.as_dict() for profile in PROFILES],
                    ensure_ascii=False,
                    indent=2,
                )
            )
        return 0
    if args.command == "freeze":
        guard = FreezeGuard(root)
        if args.action == "create":
            if not args.paths:
                raise SystemExit("freeze create requires one or more paths")
            print(guard.create(args.name, tuple(args.paths)))
        else:
            guard.verify(args.name)
            print(f"freeze '{args.name}' is intact")
        return 0
    if args.command == "install-skills":
        installed = ConversationSkillInstaller(root).install(
            args.target, scope=args.scope, force=args.force
        )
        for path in installed:
            print(path)
        return 0
    if args.command == "client-skills":
        installer = ConversationSkillInstaller(root)
        if args.action == "status":
            print(json.dumps(installer.status(args.target, scope=args.scope), indent=2))
        elif args.action == "uninstall":
            for path in installer.uninstall(args.target, scope=args.scope, force=args.force):
                print(path)
        else:
            force = args.force or args.action == "update"
            for path in installer.install(args.target, scope=args.scope, force=force):
                print(path)
        return 0
    if args.command == "doctor":
        result = Doctor(root).run(require_e2e=args.require_e2e, release=args.release)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    if args.command == "e2e":
        registry = E2ERegistry(root)
        if args.e2e_command == "record":
            print(registry.record(args.client, args.skill, args.model, args.status, args.evidence))
        else:
            print(json.dumps(registry.matrix(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "eval":
        result = CapabilityEvaluator(root).run(
            require_e2e=args.require_e2e, release=args.release
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    if args.command == "host":
        manager = HostRoundManager(root)
        if args.host_command == "begin":
            print(
                json.dumps(
                    manager.begin(
                        args.skill,
                        args.role,
                        message_file=args.message_file,
                        section=args.section,
                        venue=args.venue,
                        max_rounds=args.max_rounds,
                        sample_size=args.sample_size,
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif args.host_command == "complete":
            print(
                json.dumps(
                    manager.complete(
                        args.round_id,
                        args.decision,
                        summary=args.summary,
                        output_file=args.output_file,
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif args.host_command == "check":
            print(json.dumps(manager.check(args.round_id, args.command_name), ensure_ascii=False, indent=2))
        elif args.host_command == "approve-story":
            print(json.dumps(manager.approve_story(args.message_file), ensure_ascii=False, indent=2))
        elif args.host_command == "reset":
            print(json.dumps(manager.reset(args.skill, args.message_file), ensure_ascii=False, indent=2))
        else:
            print(json.dumps(manager.workflow.load(), ensure_ascii=False, indent=2))
        return 0

    if args.skill == "idea":
        if not args.topic:
            raise SystemExit("run idea requires --topic pointing to a Markdown document")
        TopicDocument(root).set_active(args.topic)
    elif args.skill == "write" and (not args.venue or not args.section):
        raise SystemExit("run write requires --venue and --section")
    elif args.skill == "review" and not args.venue:
        raise SystemExit("run review requires --venue")

    agent = _agent_from_args(args)
    _record_run_directive(root, args)
    research = AutoResearch(root, agent)
    if args.skill == "idea":
        _print_outcomes(research.idea_loop(str(args.topic), args.max_rounds, args.sample_size))
    elif args.skill == "story":
        _print_outcomes(research.freeze_story(args.idea, args.human_context))
    elif args.skill == "implement":
        _print_outcomes(research.implementation_loop(args.max_rounds, args.check_command))
    elif args.skill == "experiment":
        _print_outcomes(research.experiment_loop(args.max_rounds, args.run_command))
    elif args.skill == "write":
        _print_outcomes(research.write_section(args.venue, args.section, args.accepted_corpus))
    elif args.skill == "review":
        _print_outcomes(research.review(args.venue, args.venue_guide))
    return 0


if __name__ == "__main__":
    sys.exit(main())
