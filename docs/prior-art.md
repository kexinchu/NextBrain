# Open-source systems studied

The implementation learns patterns, not source code, from these projects:

- [karpathy/autoresearch](https://github.com/karpathy/autoresearch): small mutable surface,
  fixed experiment budget, one human-authored Markdown program, and keep/discard logging.
  AutoResearch generalizes the loop but retains explicit path boundaries and bounded rounds.
- [SakanaAI/AI-Scientist](https://github.com/SakanaAI/AI-Scientist): templated experiments,
  literature search, paper generation, and independent review. Its warning about executing
  LLM-written code motivates the default rule that this package never runs model-proposed
  commands.
- [SakanaAI/AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2): experiment-manager
  orchestration and progressive exploration. Its documented template-versus-open-ended
  tradeoff motivates a structured, frozen contract for implementation and experiments.
- [Agent Laboratory](https://github.com/SamuelSchmidgall/AgentLaboratory): specialized roles,
  staged literature/experiment/writing work, and human feedback between phases.
- [Orchestra Research AI-Research-SKILLs](https://github.com/Orchestra-Research/AI-Research-SKILLs):
  portable `SKILL.md` packaging with focused entry points and progressive references.

The distinguishing boundary in this repository is mechanical immutability: prompts explain
the rules, but content hashes and path allowlists enforce them.
