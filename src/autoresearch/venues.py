from __future__ import annotations

from dataclasses import asdict, dataclass


class VenueError(ValueError):
    pass


@dataclass(frozen=True)
class VenueProfile:
    canonical: str
    family: str
    aliases: tuple[str, ...]
    status: str
    official_sources: tuple[str, ...]
    contribution_focus: tuple[str, ...]
    note: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


PROFILES = (
    VenueProfile(
        "SOSP",
        "general-systems",
        ("sosp",),
        "active",
        ("https://sigops.org/s/conferences/sosp/2026/",),
        (
            "fundamental systems insight",
            "complete design and implementation",
            "rigorous evaluation and broad systems impact",
        ),
    ),
    VenueProfile(
        "FAST",
        "storage-systems",
        ("fast", "usenix fast"),
        "active",
        ("https://www.usenix.org/conference/fast26/call-for-papers",),
        (
            "storage or I/O significance",
            "failure, durability, tail-latency, and workload realism",
            "implementation evidence and artifact readiness",
        ),
    ),
    VenueProfile(
        "OSDI",
        "general-systems",
        ("osdi", "usenix osdi"),
        "active",
        ("https://www.usenix.org/conference/osdi26/call-for-papers",),
        (
            "significant systems problem and compelling solution",
            "practical implementation with quantified benefits and limitations",
            "research or operational-systems track fit",
        ),
        "The Operational Systems track can fit some practical work historically sent to ATC.",
    ),
    VenueProfile(
        "EuroSys",
        "general-systems",
        ("eurosys",),
        "active",
        ("https://2027.eurosys.org/cfp.html",),
        (
            "novel and significant systems contribution",
            "rigorous benefits-and-limitations evaluation",
            "generalizable insight, including experience papers when quantitatively supported",
        ),
    ),
    VenueProfile(
        "MLSys",
        "machine-learning-systems",
        ("mlsys", "ml systems"),
        "active",
        ("https://mlsys.org/Conferences/2026/CallForPapers",),
        (
            "machine learning and systems intersection",
            "end-to-end model, hardware, workload, and cost realism",
            "novelty and impact for research track or lessons at scale for industrial track",
        ),
    ),
    VenueProfile(
        "ICLR",
        "machine-learning",
        ("iclr",),
        "active",
        ("https://iclr.cc/Conferences/2026/CallForPapers",),
        (
            "clear machine-learning or representation-learning contribution",
            "rigorous empirical or theoretical evidence",
            "infrastructure work must expose a broadly relevant ML insight",
        ),
    ),
    VenueProfile(
        "NeurIPS",
        "machine-learning",
        ("neurips", "nips"),
        "active",
        ("https://neurips.cc/Conferences/2026/CallForPapers",),
        (
            "original and significant machine-learning contribution",
            "appropriate contribution type or track, including SysML Infrastructure",
            "rigorous evaluation with statistical and reproducibility evidence",
        ),
        "NIPS is accepted as an input alias and normalized to NeurIPS.",
    ),
    VenueProfile(
        "AAAI",
        "artificial-intelligence",
        ("aaai",),
        "active",
        ("https://aaai.org/conference/aaai/aaai-27/main-technical-track-call/",),
        (
            "distinct AI contribution and broad relevance",
            "technically sound empirical or theoretical evidence",
            "correct main or special-track fit",
        ),
    ),
    VenueProfile(
        "DAC",
        "design-automation",
        ("dac", "design automation conference"),
        "active",
        ("https://dac.com/2026/research-manuscript-submissions",),
        (
            "design-automation, hardware, systems, or software-track fit",
            "quality-of-results, PPA, runtime, and tool-flow evidence as applicable",
            "representative industrial or public benchmarks and competitive tools",
        ),
    ),
    VenueProfile(
        "USENIX ATC",
        "historical-general-systems",
        ("atc", "usenix atc"),
        "retired",
        ("https://www.usenix.org/blog/usenix-atc-announcement",),
        ("historical practical-systems writing and comparison corpus only",),
        "USENIX ATC ended after ATC '25; use an active venue for new submissions.",
    ),
)


_BY_ALIAS = {
    alias.casefold(): profile
    for profile in PROFILES
    for alias in (profile.canonical, *profile.aliases)
}


def resolve_venue(name: str, *, allow_inactive: bool = False) -> VenueProfile:
    normalized = name.strip()
    if not normalized:
        raise VenueError("venue must be non-empty")
    profile = _BY_ALIAS.get(normalized.casefold())
    if profile is None:
        return VenueProfile(
            normalized,
            "custom",
            (normalized.casefold(),),
            "active",
            (),
            ("load current official venue criteria before evaluating fit",),
            "Custom venue: current primary guidance is mandatory.",
        )
    if profile.status != "active" and not allow_inactive:
        raise VenueError(f"{profile.canonical} is {profile.status}: {profile.note}")
    return profile


def active_profiles() -> tuple[VenueProfile, ...]:
    return tuple(profile for profile in PROFILES if profile.status == "active")
