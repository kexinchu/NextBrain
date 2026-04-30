"""Configuration: load from config.yaml (primary) with env var fallbacks.

Config file search order:
  1. ./config.yaml  (project-local)
  2. ~/.nextbrain/config.yaml  (user-global)

Every field can also be set via environment variable (takes precedence over config.yaml).
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Config file loading ───────────────────────────────────────────────────────

_CONFIG_CACHE: Optional[Dict[str, Any]] = None


def _find_config_file() -> Optional[Path]:
    """Find config.yaml in CWD or ~/.nextbrain/."""
    candidates = [
        Path.cwd() / "config.yaml",
        Path.home() / ".nextbrain" / "config.yaml",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _load_config() -> Dict[str, Any]:
    """Load config.yaml into a flat dict. Cached after first call."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    path = _find_config_file()
    if path is None:
        _CONFIG_CACHE = {}
        return _CONFIG_CACHE

    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            data = {}
        _CONFIG_CACHE = data
    except Exception as e:
        print(f"[config] Warning: failed to load {path}: {e}")
        _CONFIG_CACHE = {}

    return _CONFIG_CACHE


def _get(yaml_section: str, yaml_key: str, env_var: str, default: Any = "") -> Any:
    """Get a config value. Priority: env var > config.yaml > default."""
    env_val = os.environ.get(env_var, "").strip()
    if env_val:
        return env_val
    cfg = _load_config()
    section = cfg.get(yaml_section) or {}
    if isinstance(section, dict) and yaml_key in section:
        val = section[yaml_key]
        if val is not None:
            return val
    return default


def reload_config() -> None:
    """Force reload config.yaml (useful after writing a new config file)."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None


# ── LLM ───────────────────────────────────────────────────────────────────────

def get_openai_api_key() -> str:
    return _get("llm", "api_key", "OPENAI_API_KEY", "")

def get_openai_base_url() -> Optional[str]:
    val = _get("llm", "base_url", "OPENAI_BASE_URL", "")
    return val if val else None

def get_model() -> str:
    return _get("llm", "model", "RESEARCHNOTE_MODEL", "gpt-4o-mini")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL")
MODEL = os.environ.get("RESEARCHNOTE_MODEL", "gpt-4o-mini")

# ── Browser mode ──────────────────────────────────────────────────────────────

USE_BROWSER_LLM: bool = (
    os.environ.get("RESEARCHNOTE_LLM", "").strip().lower() == "browser"
)

def set_use_browser_llm(use_browser: bool) -> None:
    global USE_BROWSER_LLM
    USE_BROWSER_LLM = use_browser

# ── Zotero ────────────────────────────────────────────────────────────────────

def get_zotero_library_id() -> str:
    return str(_get("zotero", "library_id", "ZOTERO_LIBRARY_ID", ""))

def get_zotero_api_key() -> str:
    return str(_get("zotero", "api_key", "ZOTERO_API_KEY", ""))

def get_zotero_library_type() -> str:
    return str(_get("zotero", "library_type", "ZOTERO_LIBRARY_TYPE", "user"))

# ── Obsidian ──────────────────────────────────────────────────────────────────

def get_obsidian_vault_path() -> str:
    return str(_get("obsidian", "vault_path", "RESEARCHNOTE_OBSIDIAN_VAULT",
                     str(Path.home() / "ObsidianVault")))

# ── RAG ───────────────────────────────────────────────────────────────────────

def get_rag_dir() -> str:
    return str(_get("rag", "dir", "RESEARCHNOTE_RAG_DIR",
                     str(Path.home() / ".nextbrain" / "rag")))

def get_rag_embedding_model() -> str:
    return str(_get("rag", "embedding_model", "RESEARCHNOTE_RAG_EMBEDDING_MODEL",
                     "all-MiniLM-L6-v2"))

def get_hf_token() -> Optional[str]:
    """HuggingFace token for downloading gated/private models."""
    val = _get("rag", "hf_token", "HF_TOKEN", "")
    return val if val else None

# ── Output language ───────────────────────────────────────────────────────────

def get_output_language() -> str:
    """Return configured output language: 'zh' for Chinese, 'en' for English."""
    return str(_get("output", "language", "RESEARCHNOTE_OUTPUT_LANGUAGE", "zh"))

# ── Mail ingest ───────────────────────────────────────────────────────────────

def get_mail_user() -> str:
    return str(_get("mail", "user", "RESEARCHNOTE_MAIL_USER", ""))

def get_mail_credentials_path() -> str:
    return str(_get("mail", "credentials", "RESEARCHNOTE_MAIL_CREDENTIALS",
                    str(Path.home() / ".nextbrain" / "gmail_credentials.json")))

def get_mail_token_path() -> str:
    return str(_get("mail", "token", "RESEARCHNOTE_MAIL_TOKEN",
                    str(Path.home() / ".nextbrain" / "gmail_token.json")))

def get_mail_sender_filter() -> str:
    return str(_get("mail", "sender_filter", "RESEARCHNOTE_MAIL_SENDER", ""))

def get_mail_subject_prefix() -> str:
    return str(_get("mail", "subject_prefix", "RESEARCHNOTE_MAIL_SUBJECT_PREFIX",
                    "[AI Digest]"))

def get_mail_label() -> str:
    """Optional Gmail label to filter by; default INBOX."""
    return str(_get("mail", "label", "RESEARCHNOTE_MAIL_LABEL", "INBOX"))


# ── Active topics ─────────────────────────────────────────────────────────────

def get_topics_top_k() -> int:
    return int(_get("topics", "active_top_k", "RESEARCHNOTE_TOPICS_TOP_K", 5))

def get_topics_half_life_days() -> int:
    return int(_get("topics", "decay_half_life_days", "RESEARCHNOTE_TOPICS_HALF_LIFE", 14))

def get_topics_recompute_hours() -> int:
    return int(_get("topics", "recompute_after_hours", "RESEARCHNOTE_TOPICS_RECOMPUTE", 24))

def get_topics_cache_path() -> str:
    return str(_get("topics", "cache_path", "RESEARCHNOTE_TOPICS_CACHE",
                    str(Path.home() / ".nextbrain" / "active_topics.json")))

# ── Filter / Prune ────────────────────────────────────────────────────────────

def get_filter_rag_dup_threshold() -> float:
    return float(_get("filter", "rag_dup_threshold", "RESEARCHNOTE_FILTER_DUP", 0.92))

def get_filter_min_topic_score() -> float:
    return float(_get("filter", "min_topic_score", "RESEARCHNOTE_FILTER_MIN_TOPIC", 0.5))

def get_prune_unread_threshold_days() -> int:
    return int(_get("prune", "unread_threshold_days", "RESEARCHNOTE_PRUNE_UNREAD", 90))

def get_prune_inbox_threshold_days() -> int:
    return int(_get("prune", "inbox_threshold_days", "RESEARCHNOTE_PRUNE_INBOX", 14))

def get_archive_dir_name() -> str:
    return str(_get("prune", "archive_dir", "RESEARCHNOTE_ARCHIVE_DIR", "Archive"))


# ── Paper type taxonomy ───────────────────────────────────────────────────────

DEFAULT_PAPER_TYPES: List[str] = [
    "ANNS",
    "RAG",
    "Diffusion-Language-Model",
    "LLM-Opt",
    "Agentic-OS",
    "KV-Cache",
    "LLM-Security",
    "Memory",
    "Deterministic-LLM",
    "Other",
]

def get_paper_types() -> List[str]:
    """Return configured paper types."""
    env = os.environ.get("RESEARCHNOTE_PAPER_TYPES", "").strip()
    if env:
        return [t.strip() for t in env.split(",") if t.strip()]
    cfg = _load_config()
    types = (cfg.get("paper_types") or cfg.get("taxonomy", {}).get("paper_types"))
    if types and isinstance(types, list):
        return types
    return DEFAULT_PAPER_TYPES


# ── Config file template ─────────────────────────────────────────────────────

CONFIG_TEMPLATE = """\
# ResearchNote Configuration
# Place this file at ./config.yaml (project-local) or ~/.nextbrain/config.yaml (global)
# All fields can also be set via environment variables (env vars take precedence)

# ── LLM ──────────────────────────────────────────────────────────────────────
# Required: at least api_key must be set (here or via OPENAI_API_KEY env var)
llm:
  api_key: ""                      # OpenAI API key (or compatible provider key)
                                    # Env: OPENAI_API_KEY
  base_url: ""                     # Custom API endpoint (leave empty for OpenAI default)
                                    # Env: OPENAI_BASE_URL
  model: "gpt-4o-mini"            # Model name
                                    # Env: RESEARCHNOTE_MODEL

# ── Zotero ───────────────────────────────────────────────────────────────────
# Optional but recommended. If not configured, paper recording skips Zotero.
zotero:
  api_key: ""                      # Zotero API key  (Env: ZOTERO_API_KEY)
  library_id: ""                   # Your Zotero user ID (numeric)  (Env: ZOTERO_LIBRARY_ID)
  library_type: "user"             # "user" for personal library, "group" for shared

# ── Obsidian ─────────────────────────────────────────────────────────────────
# Required: path to your Obsidian vault folder.
# ResearchNote writes paper notes to Papers-<paper_type>/ and idea notes to Idea/.
# For a fuller PhD workspace (Concepts, Projects, Syntheses, Daily, etc.),
# run: nextbrain workspace-init
obsidian:
  vault_path: "~/ObsidianVault"    # Absolute path to your Obsidian vault
                                    # Env: RESEARCHNOTE_OBSIDIAN_VAULT

# ── RAG ──────────────────────────────────────────────────────────────────────
# Optional. Enables semantic search across your notes.
# Requires: pip install nextbrain[rag]
# After configuration, run: nextbrain index
rag:
  dir: "~/.nextbrain/rag"      # ChromaDB vector database path
                                    # Env: RESEARCHNOTE_RAG_DIR
  embedding_model: "all-MiniLM-L6-v2"
  hf_token: ""                    # HuggingFace token (Env: HF_TOKEN)

# ── Output ──────────────────────────────────────────────────────────────────
output:
  language: "zh"                   # "zh" (Chinese) or "en" (English)
                                    # Env: RESEARCHNOTE_OUTPUT_LANGUAGE

# ── Paper Type Taxonomy ──────────────────────────────────────────────────────
paper_types:
  - ANNS
  - RAG
  - Diffusion-Language-Model
  - LLM-Opt
  - Agentic-OS
  - KV-Cache
  - LLM-Security
  - Memory
  - Deterministic-LLM
  - Other

# ── Mail ingest (optional) ────────────────────────────────────────────────────
# For `nextbrain ingest-mail` — pulls AI Digest emails via Gmail API.
# Requires: pip install nextbrain[ingest]
# Setup:
#   1. Create OAuth client at console.cloud.google.com (Desktop app),
#      download credentials.json to the path below.
#   2. First run will open a browser for consent; token cached afterwards.
mail:
  user: ""                                 # Your Gmail address
  credentials: "~/.nextbrain/gmail_credentials.json"
  token: "~/.nextbrain/gmail_token.json"
  sender_filter: ""                        # Only ingest emails from this sender
  subject_prefix: "[AI Digest]"            # Subject must start with this
  label: "INBOX"                           # Gmail label to scan
  processed_label: "ResearchNote/Processed"  # Applied after successful ingest

# ── Active-topic inference ────────────────────────────────────────────────────
topics:
  active_top_k: 5
  decay_half_life_days: 14                 # Recency weight half-life
  recompute_after_hours: 24                # Cache TTL
  cache_path: "~/.nextbrain/active_topics.json"

# ── Filter (second-stage on ingest) ───────────────────────────────────────────
filter:
  rag_dup_threshold: 0.92                  # Cosine sim >= → flag duplicate-of, route to Inbox/
  min_topic_score: 0.5                     # Upstream topic-tag score below this → Inbox/

# ── Prune ─────────────────────────────────────────────────────────────────────
prune:
  unread_threshold_days: 90                # Unread+unreferenced for this many days → prunable
  inbox_threshold_days: 14                 # Inbox/ items older than this → prunable
  archive_dir: "Archive"                   # Relative to vault; pruned notes moved here
"""
