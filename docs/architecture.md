# Architecture

AutoResearch is a deterministic state machine around nondeterministic agents.

```text
user messages -> immutable Markdown journal -----+
       |                                          |
       +-> active topic.md (session mirror) -> requirements digest
                                                  |
                                                  v
idea scout <-> risk-sampled challenger -> story.md -> paper/STORY.md -> implementation -> experiments
                                         schema       approval+freeze     check+freeze
```

## Topic and session requirements

`.autoresearch/active-topic.json` points to the active topic Markdown. Every user message
and run directive is mirrored into that file and separately stored under
`requirements/messages/`. Switching to another topic document synchronizes existing session
requirements into it.

Before every agent call, the immutable source records are hash-verified. Their digest is
combined with the active topic document digest. The response must echo that digest and name
possible drift. The orchestrator writes a prompt, output, manifest, and alignment report for
every round. If requirements change during an agent call, the round stops with `report`.

## Editable idea story

The idea roles return a complete Markdown `story` field. The orchestrator writes it to the
root-level `story.md`. A later invocation reads the current file before proposing or
challenging anything, so a human can directly revise scope, framing, or open questions.

## Transaction, path, and execution policy

Conversation skills write into `.autoresearch/transactions/<round>/workspace`. The host
validates a per-round evidence manifest and promotes only allowlisted regular files. Direct
main-workspace changes are copied to quarantine and the governed pre-round version is
restored. Symlinks, staged deletions, path traversal, unrelated output files, and reused old
review/result artifacts are rejected.

Commands are selected by name from the human-authored `autoresearch.yaml`; the model cannot
supply argv to the check runner. Check receipts include argv, exit code, stdout, and stderr.

## Freeze model

`story-freeze` turns editable `story.md` into `paper/STORY.md` and hashes the latter.
Implementation rounds verify that hash before and after applying files. Once implementation
succeeds, `code/core/` is hashed. Experiment rounds verify both hashes before and after every
agent call.

Writing deliberately edits `paper/manuscript/<section>.md`, not `paper/STORY.md`. This makes
"improve prose without changing the frozen initial paper" mechanically meaningful.

## Structured scientific state

Human-readable story Markdown carries YAML frontmatter with stable candidate, source,
claim, and experiment identifiers. Referential validation prevents dangling claim/evidence
links. Challenger samples are risk-ranked while preserving approach diversity. Experiment
completion covers the exact frozen matrix; contradiction status forces a human report.

Workspace snapshots use a stat-aware digest cache and governed path set. Large data roots
configured under `snapshot.exclude` are treated as inputs, avoiding full dataset hashing on
every round, while requirements and frozen paper/core files are always rehashed.

## Backend model

Conversation-native skills use the model already selected in GPT/Codex, Claude, or Cursor.
They begin a guarded host round, let that model reason and edit with the host's own tools,
and then complete the round so Python can verify requirements, freezes, and changed paths.
No model API is selected by the skill. See [Conversation hosts](conversation-hosts.md).

For non-conversation automation, the optional standalone path uses one
`Agent.complete(request)` protocol. The bundled adapters are:

- `CommandAgent`: invokes any user-selected local coding/research agent, passes the prompt
  on stdin, and receives JSON on stdout.
- `OpenAIAgent`: optional Responses API adapter installed with the `openai` extra.

The deterministic state layer does not depend on a particular agent framework. The
standalone adapters are never used by a conversation-native skill.
