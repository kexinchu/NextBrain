---
name: venue-review
description: Produce a new evidence-grounded venue review in staging, preferably with an independent host-native reviewer subagent.
version: 0.3.0
model: inherit
---

# Venue review

Use the current conversation model; do not call another model API or `autoresearch run`.
Record the exact user message and begin a `venue-reviewer` round bound to the latest message. Use a fresh
host-native reviewer subagent when available and record its host run ID; otherwise disclose
the reduced independence.

```text
autoresearch host begin --skill venue-review --role venue-reviewer \
  --venue <venue> --message-file <latest-message>
```

Read current venue criteria from primary sources, the full manuscript, frozen story,
results, and all requirements. Do not edit any paper file. Write a new review under the
transaction workspace's `reviews/` directory; existing reviews are not copied in, so an old
artifact cannot satisfy this round.

Apply the selected venue-family focus from the host prompt. In particular, distinguish a
systems contribution from an ML-algorithm contribution, an MLSys end-to-end contribution,
and a DAC design-automation contribution. A paper that is sound but aimed at the wrong
community receives an explicit venue-fit blocker. Refresh the current official CFP,
author instructions, and reviewer guidance instead of relying on a remembered year.

Evaluate significance, novelty/collision, scope, correctness, claim/evidence alignment,
baseline fairness, completeness, reproducibility, ethics, writing, and venue fit. Separate
submission blockers, required changes, and optional polish. Give exact locations and
paste-ready comments; missing evidence remains missing.

The evidence manifest lists the newly created review artifact, exact bound `venue`, current
`venue_guidance_sources` with title, URL, and access date, plus a `reviewer` mapping. Set its
mode to `independent-subagent` with a host agent ID, or `current-model` to disclose reduced
independence. Complete with that same logical path as `--output-file`. The host rejects
unrelated output files and satisfaction without a new review artifact.
