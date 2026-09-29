# ResearchOS V0.3 validation and pilot admission

## Delivered behavior

This milestone adds an opt-in research intelligence layer on merged master `e926472`
(PR #4). Execution, recovery, named commands, frozen source, artifact verification,
resource reservations and human approval mechanisms are reused.

New behavior includes typed question graphs, competing hypotheses, blocking uncertainty,
ORACLE experiments and motivation prerequisites, explicit reasoning cycles, ordinal candidate
ranking, rich frozen predictions, separately prompted challenger support, surprise-driven
uncertainties and bounded child proposals, research debt, claim-specific maturity, expanded
Gate #2 reviews, SQLite-derived journals and text trajectories.

The attachment is recorded verbatim in the immutable requirement journal. Its last section
ends at test item 8; no missing tail was assumed. No paper story was written or frozen.

## Automated verification

- Deterministic pytest suite: 162 tests, including 41 V0.3 contract/integration cases.
- Ruff, wheel/sdist build, installed wheel CLI and skill listing, release doctor.
- Existing migration coverage now verifies schema 4 without losing legacy records.
- Offline planner cases A–E use no model provider, network, or job execution.
- Installed CLI smoke enables V0.3 and runs the existing bounded CPU validation flow.

The source-independent wheel smoke completed one run, then two runs, then stopped at the
approved synthetic budget. It recorded **3 Findings and 10 planning records**, with no
repeated fixture starts. All findings remain SYSTEM_VALIDATION; the hypothesis stays PROPOSED.
This establishes integration with the executor, not a scientific result.

Evidence summaries:

- [Planner evaluation](validation/v03-planner-evaluation.json)
- [Installed CLI validation](validation/v03-installed-cli.json)
- [Pilot admission](validation/v03-pilot-admission.json)

| Case | Structural property checked |
| --- | --- |
| A | Motivation measurement selected before premature optimization |
| B | Negligible simulated oracle opportunity blocks implementation |
| C | Unreplicated central debt selects replication and blocks expansion |
| D | Controlled discrimination selected; correlated performance alone rejected |
| E | Unexpected observation creates an uncertainty without rewriting frozen prediction |

Case fixtures may initialize simulated scientific states in disposable catalogs to exercise
production policy. They are explicitly labeled and never admitted to a real project catalog.
The integration tests separately use local executor receipts to verify interpretation paths.
No external LLM research-quality evaluation was run. Structural correctness does not establish
that a language model now proposes better research ideas.

## Real-project pilot: Human Gate #1 required

Read-only inspection of:

`/Users/kexin.chu/Github/paper-manager/Ideas/Research-Map/plans/`

found one Markdown file, `2026-09-27-pursue-verdicts.md`. Its content SHA-256 was:

`6e7011e5f02b984ff3ccfaf14dbc9a396a6322f6d2597208c442f5c2e6312992`

The file recommends pursuing five candidates (B-04, B-07, B-09, B-03, B-11) and proposes
premise tests. It contains no explicit approved GO decision. Recommendations and rankings
were not promoted into approval. **No real project was selected; S5/S6 planning and scientific
execution stopped at Human Gate #1.** The upstream file was not modified.

Next required input is a human GO decision identifying one seed. A real envelope and S5/S6
artifacts can then be prepared for that approved seed, including its motivation and oracle
experiments. Substantial GPU work still requires review before dispatch.

## Operational boundaries and remaining limits

- No remote machines, credentials, SSH trust or server storage were changed for V0.3.
- No GPU science, automatic merge, literature scope expansion or paper approval occurred.
- The original dirty checkout was preserved; work used an isolated branch based on master.
- Ordinal ratings, causal labels and challenger prose remain researcher judgments. The system
  validates structure and evidence provenance, not semantic truth or novelty.
- New child proposals preserve parent, question, envelope and budget references. Free-text
  scope relevance still needs scientific judgment; children cannot grant execution authority.
- Only verified replication automatically resolves its corresponding debt. Other debt stays
  visible for human review; there is no generic model-controlled debt-dismissal command.
- Gate continuation choices record human intent and permit replanning; they do not generate
  a new experiment pool or automatically enforce a chosen research focus.
- External provider adapters must bound their own request latency. The bundled adapter limits
  candidate/challenger counts and stores separate prompt audits; it does not bundle an SDK.
