"""IO: load/save artifacts with validation."""
import json
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> Any:
    path = Path(path)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: Any, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_yaml(path: str | Path) -> Any:
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML required for YAML: pip install pyyaml")
    path = Path(path)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_yaml(data: Any, path: str | Path) -> None:
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML required for YAML: pip install pyyaml")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def write_markdown(path: str | Path, content: str) -> None:
    """Write markdown content to file, creating parent dirs if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_markdown(path: str | Path) -> str | None:
    """Read markdown file, return None if not exists."""
    path = Path(path)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")
