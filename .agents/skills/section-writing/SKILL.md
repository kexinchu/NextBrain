---
name: section-writing
description: Rewrite one section in staging after experiments, with explicit evidence that every frozen claim is preserved and no new claim is introduced.
version: 0.4.0
model: inherit
---

# Section writing

Use the current conversation model and never call a second model API or `autoresearch run`.
Record the exact user message, choose one simple section name, and run:

```text
autoresearch host begin --skill section-writing --role section-writer \
  --section <name> --venue <venue> --message-file <latest-message>
```

This stage requires completed experiments. Read the frozen story, results, venue rules,
adjacent sections, and a bounded primary-source sample of relevant papers accepted by the
venue in the previous calendar year. Record source title, URL, venue, year, and access date.
Learn organization and evidence presentation without copying prose.

Use the canonical venue and family returned in the host prompt. For systems venues,
prioritize problem significance, design insight, implementation completeness, fair systems
baselines, scale, overheads, and limitations. For MLSys/ICLR/NeurIPS/AAAI, make the ML or AI
contribution legible without disguising systems evidence as algorithmic novelty. For DAC,
make the design-automation or hardware-flow contribution and quality-of-results evidence
explicit. Never reuse a style profile without reading the current official guidance.

Edit only `transaction_workspace` staged `paper/manuscript/<name>.md`. Preserve design, metric definitions, result
values, and every frozen claim ID. If better prose needs new science, report it instead.

The evidence manifest names the section artifact, lists every frozen ID in
`preserved_claim_ids`, sets `new_claims` to an empty list, and records the accepted-paper
style corpus in `style_sources` with title, URL, bound venue, year, and access date. It also
repeats the exact bound `venue`. This claim-preservation evidence is mandatory for every
non-blocked round, including `continue`. Complete with the staged section as `--output-file`.
The host rejects missing claim coverage, new claims, unrelated outputs, or unchanged old
artifacts.
