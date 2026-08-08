# Venue profiles for systems and AI infrastructure

The repository has two priority tiers in `autoresearch.yaml`:

- Primary systems/AI-infrastructure targets: SOSP, FAST, OSDI, EuroSys, MLSys.
- Secondary targets when the scientific contribution genuinely fits: ICLR, NeurIPS, AAAI,
  DAC.

`NIPS` is accepted as an alias and normalized to `NeurIPS`. USENIX ATC is historical-only:
USENIX announced that ATC '25 was the final conference. For practical general-systems work,
the current OSDI call should be checked, including its Operational Systems track.

| Venue | Family | Default fit gate | Seed official source |
|---|---|---|---|
| SOSP | General systems | Fundamental systems insight, implementation, broad impact | [SOSP 2026](https://sigops.org/s/conferences/sosp/2026/) |
| FAST | Storage systems | Storage/I/O significance, realistic workloads, failures and durability | [FAST '26 CFP](https://www.usenix.org/conference/fast26/call-for-papers) |
| OSDI | General systems | Significant problem, compelling implemented solution, quantified tradeoffs | [OSDI '26 CFP](https://www.usenix.org/conference/osdi26/call-for-papers) |
| EuroSys | General systems | Novel systems contribution and rigorous benefits/limitations | [EuroSys 2027 CFP](https://2027.eurosys.org/cfp.html) |
| MLSys | ML systems | End-to-end ML/system contribution using real models, hardware, workloads, cost | [MLSys 2026 CFP](https://mlsys.org/Conferences/2026/CallForPapers) |
| ICLR | Machine learning | Broadly relevant ML insight, not infrastructure performance alone | [ICLR 2026 CFP](https://iclr.cc/Conferences/2026/CallForPapers) |
| NeurIPS | Machine learning | Original ML contribution or correct track/contribution type, including SysML Infrastructure | [NeurIPS 2026 CFP](https://neurips.cc/Conferences/2026/CallForPapers) |
| AAAI | Artificial intelligence | Distinct AI contribution and correct main/special-track fit | [AAAI-27 Main Track](https://aaai.org/conference/aaai/aaai-27/main-technical-track-call/) |
| DAC | Design automation | EDA/hardware/system fit with relevant QoR, PPA, runtime, flow, and benchmark evidence | [DAC 2026 Research Manuscripts](https://dac.com/2026/research-manuscript-submissions) |
| USENIX ATC | Historical systems | Style and prior-work corpus only; not a new submission target | [USENIX ATC announcement](https://www.usenix.org/blog/usenix-atc-announcement) |

These links are discovery seeds, not frozen submission rules. For every writing or review
round, record the current official CFP, author instructions, reviewer guidance, selected
track, access date, and the accepted-paper corpus actually studied. If the current source
disagrees with a built-in profile, stop and report the stale profile instead of silently
using it.
