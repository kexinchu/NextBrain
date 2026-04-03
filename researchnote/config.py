"""Configuration: load from config.yaml (primary) with env var fallbacks.

Config file search order:
  1. ./config.yaml  (project-local)
  2. ~/.researchnote/config.yaml  (user-global)

Every field can also be set via environment variable (takes precedence over config.yaml).
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Config file loading ───────────────────────────────────────────────────────

_CONFIG_CACHE: Optional[Dict[str, Any]] = None


def _find_config_file() -> Optional[Path]:
    """Find config.yaml in CWD or ~/.researchnote/."""
    candidates = [
        Path.cwd() / "config.yaml",
        Path.home() / ".researchnote" / "config.yaml",
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
                     str(Path.home() / ".researchnote" / "rag")))

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
# Place this file at ./config.yaml (project-local) or ~/.researchnote/config.yaml (global)
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
# ResearchNote creates folders: Papers-<paper_type>/, Idea/
obsidian:
  vault_path: "~/ObsidianVault"    # Absolute path to your Obsidian vault
                                    # Env: RESEARCHNOTE_OBSIDIAN_VAULT

# ── RAG ──────────────────────────────────────────────────────────────────────
# Optional. Enables semantic search across your notes.
# Requires: pip install researchnote[rag]
# After configuration, run: researchnote index
rag:
  dir: "~/.researchnote/rag"      # ChromaDB vector database path
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
"""
