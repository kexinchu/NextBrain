"""Web search tool wrapper (pluggable). Returns list of {title, snippet, url}."""
from typing import List, Dict, Any

def search(query: str, max_results: int = 10, **kwargs: Any) -> List[Dict[str, str]]:
    """
    Pluggable web search. Override this or set env to use a real API.
    MVP: returns placeholder results so pipeline runs end-to-end.
    """
    # Placeholder for MVP: no API key required
    return [
        {
            "title": f"[Placeholder] Paper related to: {query[:50]}...",
            "snippet": "Placeholder snippet for literature. Set a real search backend for production.",
            "url": "https://example.com/placeholder",
        }
        for _ in range(min(3, max_results))
    ]
