"""LLM caller (OpenAI-compatible) for agents."""
import json
import re
from typing import Any, Optional

def get_client():
    from openai import OpenAI
    import config
    kwargs = {"api_key": config.OPENAI_API_KEY or "sk-placeholder"}
    if config.OPENAI_BASE_URL:
        kwargs["base_url"] = config.OPENAI_BASE_URL
    return OpenAI(**kwargs)

def get_model() -> str:
    import config
    return config.MODEL

def call_llm(
    system: str,
    user: str,
    model: Optional[str] = None,
    json_mode: bool = False,
) -> str:
    """Returns assistant text. If json_mode, tries to parse and return cleaned JSON string."""
    client = get_client()
    model = model or get_model()
    kwargs: Any = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    r = client.chat.completions.create(**kwargs)
    text = r.choices[0].message.content or ""
    if json_mode:
        # Extract JSON block if wrapped in markdown
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
        try:
            json.loads(text)
        except json.JSONDecodeError:
            pass
    return text
