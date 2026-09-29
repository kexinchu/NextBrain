# ResearchOS V0.3: research intelligence

V0.3 extends the existing planner and executor. SQLite remains authoritative. Enable the
new contracts per project by registering a core question matching the approved envelope:

```yaml
id: Q1
question: Exact problem text from the approved Project Envelope
motivation_hypotheses: [H1]
oracle_hypotheses: [H2]
```

```bash
researchos research question PROJECT --file question.yaml
researchos research edge PROJECT --file edge.yaml
researchos research debt PROJECT --file debt.yaml
researchos planner import PROJECT --file proposals.yaml
researchos next PROJECT
researchos research maturity PROJECT
researchos journal PROJECT
researchos trajectory PROJECT
```

Legacy projects without a registered question retain V0.2 behavior. SQLite migrates to
schema 4 without rewriting existing immutable hypotheses or experiment freezes. Register
new typed hypotheses before enabling V0.3 for an old project. Package version stays 0.4.0.

## Questions, hypotheses and uncertainties

Hypothesis `hypothesis_type` is EXISTENCE, MECHANISM, CAUSAL, PERFORMANCE, BOUNDARY or
GENERALIZATION. `UNCLASSIFIED` remains valid for legacy imports but cannot be executed as
a V0.3 candidate. A performance benchmark alone cannot establish mechanism or causality.

Edges use typed references and remain within one project:

```yaml
source: {kind: hypothesis, id: H3}
target: {kind: hypothesis, id: H2}
relation: DEPENDS_ON
reason: Implementation only matters if the oracle has useful headroom.
```

Kinds: question, hypothesis, uncertainty, experiment, finding, claim. Relations: SUPPORTS,
CONTRADICTS, DEPENDS_ON, ALTERNATIVE_TO, EXPLAINS, REFINES. Dependency cycles are rejected.
Relations express reasoning, not evidence certification. DEPENDS_ON hypotheses must be
supported and uncertainties resolved before dependent experiments are admitted.

Uncertainties additionally accept `blocks: [{kind: hypothesis, id: H3}]` and ordinal
`decision_relevance`, `current_uncertainty`, `risk_to_project`. Blocking uncertainties
must be resolved before downstream work; an experiment addressing that uncertainty itself
can proceed. Checks read complete durable state even when model context is truncated.

## Reasoning and experiment design

Every proposal bundle adds `reasoning_cycle` with substantive text for:
`observe`, `current_belief`, `uncertain`, `competing_explanations`, `change_our_mind`,
`cheapest_decisive_experiment`, `predicted_outcomes`.

Each V0.2 candidate adds the following `research` record:

```yaml
research:
  strategy: CONTROLLED_INTERVENTION
  competing_hypotheses: [H4]
  central: true
  cheap_falsification: true
  falsification_exemption: ''
  value:
    decision_relevance: HIGH
    uncertainty_reduction: HIGH
    discrimination_power: HIGH
    downstream_unlock_value: HIGH
    feasibility: MEDIUM
    compute_cost: LOW
    implementation_cost: LOW
    execution_risk: LOW
  prediction:
    expected:
      transfer_bytes: {direction: decrease, range: [1000, 2000]}
    mechanism: Reusing the controlled prefix eliminates repeated transfers.
    boundary: Fixed request set and batch composition in the approved workload.
    surprising_result: Lower latency without reduced transfer bytes.
    falsification: Transfer bytes remain above the predeclared bound.
  challenger:
    prompt_role: challenger
    alternative_explanation: Batch composition caused the latency change.
    confounder: Uncontrolled cache state.
    strong_baseline: The approved caching baseline with the same warmup.
    falsification_test: Disable reuse while holding the request set fixed.
    mechanism_measurement: Measure transfer bytes alongside latency.
    verdict: PASS
```

Strategies also include MEASUREMENT, ORACLE, COUNTERFACTUAL, ABLATION, STRESS_TEST,
TRACE_ANALYSIS, MICROBENCHMARK, END_TO_END, REPLICATION. ORACLE is an experiment type and
requires the ORACLE strategy. Outcome interpretations remain mandatory for SUPPORTED,
FALSIFIED, INCONCLUSIVE and OPERATIONAL_FAILURE.

Each uncertainty's candidate group needs a cheap falsification attempt or an explicit
exemption explaining why it is inappropriate. Central and PRIMARY experiments require a
challenger; REVISE blocks admission. Registered motivation/oracle premises block expensive
implementation and optimization until supported. No new command or execution privileges
are granted. Freeze, run creation and dispatch recheck V0.3 design admission.

Ordinal priority compares upstream blockers, decision relevance, current uncertainty,
project risk, benefit/cost band, cheap falsification, discrimination, then compute cost.
Components are auditable qualitative judgments, not calibrated information gain. Existing
runtime reservations enforce actual compute limits independently of these judgments.

`PromptedReasoner(generate)` is optional. Its injected provider function receives `role`,
`prompt`, `context`; it calls the planner once and challenger separately for each central
candidate, at most 12. Planning records preserve prompt and input/output digest audit.
The provider must impose its own request timeout; no SDK, credentials, retry loop or hidden
network calls are introduced. The CLI uses stored proposals by default. Imported challenger
records are declarations supplied by the caller; the catalog cannot prove who authored them.

## Interpretation, branching and debt

Predictions are copied into the immutable experiment freeze. Numeric ranges use the same
units as measured metrics; use null when a range is not defensible. Without a baseline,
prose direction alone is not numerically assessed. Results classify as EXPECTED,
PARTIALLY_EXPECTED, SURPRISING or STRONGLY_CONTRADICTORY. Missing metrics stay unassessed.

Only executor-verified scientific Findings trigger scientific interpretation. An unexpected
range departure creates one deterministic uncertainty and HIGH anomaly debt. Retrying
interpretation does not duplicate them. Synthetic infrastructure validation creates neither.

`research branch PROJECT --file branch.yaml` admits a proposed child hypothesis and
uncertainty atomically. Required fields are finding_id, current state_digest,
envelope_digest, question_id, budget_delta (exactly zero), parent_hypothesis, reason,
hypothesis and uncertainty. The Finding must be surprising scientific evidence for that
parent. Child hypothesis fields: id, statement, falsification_condition, hypothesis_type.
Child uncertainty fields: id, question, importance, why_it_matters. The child starts PROPOSED,
linked by REFINES, and grants no execution or approval. Stale state, changed question or
budget, extra fields and unrelated parents are rejected. Free-text semantic relevance still
requires researcher judgment; later execution remains constrained by the unchanged envelope.

Debt has kind, severity, reason, hypothesis_ids, finding_ids. Kinds: MISSING_BASELINE,
UNREPLICATED_CENTRAL_RESULT, UNEXPLAINED_ANOMALY, WORKLOAD_REALISM, WEAK_MOTIVATION,
MISSING_SENSITIVITY, MEASUREMENT_INSTABILITY, LITERATURE_CHECK_REQUIRED. HIGH debt restricts
related candidates to repair experiment types; empty hypothesis_ids makes it project-wide.
A preliminary central positive creates replication debt; verified independent replication
can resolve it. Other debt is retained for human review, with no generic model-driven resolve
operation. Literature debt never authorizes a new baseline or scope expansion.

## Maturity and human review

Claims may declare hypothesis_ids and maturity_requirements drawn from MOTIVATION,
PRELIMINARY, REPLICATED, MECHANISM_ISOLATED, BOUNDARY, END_TO_END. Requirements are claim-specific.
Mechanism maturity requires an intervention/counterfactual/ablation strategy. End-to-end
maturity requires PRIMARY with END_TO_END strategy. Relevant contradictory findings block
readiness. No configured claim requirements means paper readiness remains false.

Gate #2 includes original/current beliefs, strongest evidence, surprises, remaining debt,
claim maturity, changes in understanding, remaining opportunities and conservative compute
reservations. Reservations are not measured consumption. FREEZE_STORY additionally requires
all declared claim requirements and no HIGH debt, including debt omitted from model context.

Gate choices include CONTINUE_EXPLORATION, FOCUS_MECHANISM, REPLICATE, EXPAND_EVALUATION,
STOP_PROJECT, REQUEST_SCOPE_CHANGE, FREEZE_STORY. Human receipt text binds the exact action
and digest (`APPROVE gate:REPLICATE DIGEST`). The four continue choices authorize continuation;
they do not bypass planner policy or create candidates. Scope changes still need a revised
approved envelope. No paper story is frozen automatically.

The context is capped at 64 KiB and prioritizes contradictions, central evidence and blockers.
The journal and trajectory are generated from structured SQLite records; editing their
Markdown output does not change research state.

## Evaluation and real-project admission

```bash
researchos evaluate-planner --cases evaluations/research_planner_cases.json
researchos pilot-check --plans /path/to/upstream/plans
```

The evaluator runs A–E in disposable simulated catalogs, uses production planner policy and
result interpretation, and exits nonzero on a failed case. Fixture belief/evidence records
are explicitly simulated; no jobs run and no external model is called. This tests structural
reasoning contracts, not an empirical improvement in LLM research quality. Provider evaluations
remain optional and separate from reproducible CI.

Pilot admission reads Markdown frontmatter with idea_id, decision: GO, and approval.actor /
approval.message. It never treats rankings, pursue recommendations or bare GO prose as a
human decision. If another upstream format carries a human decision, review and import its
receipt explicitly. `pilot-check` neither creates a GO nor dispatches work. See the
[V0.3 validation report](researchos-v03-validation.md) for the current blocked real pilot.
