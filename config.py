"""Configuration: LLM and API keys (env or defaults)."""
import os

# LLM: set OPENAI_API_KEY or use base_url for local/compatible endpoints
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", None)  # e.g. http://localhost:8000/v1
MODEL = os.environ.get("EFFICIENT_RESEARCH_MODEL", "gpt-4o-mini")
