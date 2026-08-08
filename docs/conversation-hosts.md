# Conversation-native installation

The six skills use the model already selected in the current conversation. They do not
need an API key and do not select or invoke a second model. The package's older
`autoresearch run` command remains an optional standalone adapter mode; conversation skills
explicitly prohibit it.

## Install the package and skills

From a checkout:

```bash
python -m pip install .
autoresearch --workspace /path/to/research init
cd /path/to/research
autoresearch install-skills --target all --scope project
```

The final command installs the same portable sources into each client's project directory:

```text
.agents/skills/<skill>/SKILL.md   # GPT/ChatGPT desktop and Codex
.claude/skills/<skill>/SKILL.md   # Claude Code
.cursor/skills/<skill>/SKILL.md   # Cursor
```

Use `--target gpt`, `codex`, `claude`, or `cursor` to install only one surface. Use
`--scope user` for the client's user-level skills directory. Existing skills are preserved
unless `--force` is explicitly supplied.

## Invoke from a conversation

- GPT/ChatGPT desktop: select the skill with `@` when available.
- Codex CLI or IDE: use `/skills` or `$idea-loop`.
- Claude Code: use `/idea-loop` or let Claude select it from the description.
- Cursor: use `/idea-loop` or let the agent select it from the description.

Cursor currently documents Agent Skills as a Nightly-channel feature. If the stable build
does not discover `.cursor/skills/`, switch the update channel to Nightly and restart.

The YAML field `model: inherit` makes the Claude copy explicitly inherit the conversation
model. GPT/Codex and Cursor receive the same instruction in the skill body: the host's
currently selected model performs all reasoning and editing.

The `idea-loop` requires two fresh host-native subagents. If a particular client or mode
does not expose subagent delegation, the skill stops and reports the missing capability; it
does not silently call another provider or simulate two independent agents in one trace.

Configured venue priorities and aliases are available through `autoresearch venues list`.
Venue-dependent rounds canonicalize aliases, reject retired targets, require the selected
venue to appear in the frozen story contract, and inject the configured venue-family focus
into the host prompt. They still must refresh the current official guidance at runtime.

## Per-turn and per-round protocol

For every new instruction handled by a skill:

1. The host saves the exact message to a temporary Markdown file and calls
   `autoresearch message --file ...`. The journal stores one immutable Markdown source and
   mirrors it into the active topic document.
2. Before each role or loop iteration, the host calls `autoresearch host begin` with the
   latest message filename. This verifies stage order, role alternation, requirements, and
   freezes, then creates an isolated transaction workspace.
3. The current conversation model edits only staged paths and writes the returned evidence
   manifest. Test and experiment commands can run only by configured name through
   `autoresearch host check`; their argv comes from the human-authored `autoresearch.yaml`,
   and the receipt is bound to the final staged content digest.
4. `autoresearch host complete` validates the evidence and artifact schemas before atomic
   promotion. It re-hashes all governed content, even when size and timestamps are
   unchanged. Direct main-workspace edits are quarantined and restored.

Only one round may be pending, so concurrent human edits during a transaction are forbidden.
This exclusivity lets the host recover the pre-round governed files without silently losing
an authorized concurrent change.

## Readiness and real-client evidence

`autoresearch doctor` checks config, message integrity, active topic, skill drift, pending
rounds, and freezes. `autoresearch eval` runs local capability gates. These are not a claim
of real client compatibility. Record model/client evidence with `autoresearch e2e record`,
then use `doctor --require-e2e` for the 18-cell client-by-skill gate.

## ChatGPT web distribution

The repository includes `.codex-plugin/plugin.json` so it can be packaged as a local Codex
plugin. Installing a skill into ChatGPT web for a team requires the applicable ChatGPT
workspace/plugin distribution flow; `pip install` alone cannot publish a server-side skill
to that workspace.
