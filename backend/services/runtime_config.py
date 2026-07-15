"""Runtime API configuration — the single source of truth for LLM API credentials.

Values are persisted to data/runtime_config.json and survive restarts.
Users configure these through the Settings panel (⚙️) in the UI.
If no config file exists, the app starts with empty config.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "runtime_config.json"


@dataclass
class RuntimeConfigStore:
    """LLM API config — the only place credentials are stored."""

    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model_name: str | None = None

    def __post_init__(self):
        self._load()

    def _load(self) -> None:
        """Load from JSON on startup. No file means blank config — user fills via UI."""
        try:
            if CONFIG_FILE.exists():
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                if data.get("llm_api_key") and data["llm_api_key"] != "***":
                    self.llm_api_key = data["llm_api_key"]
                if data.get("llm_base_url"):
                    self.llm_base_url = data["llm_base_url"]
                if data.get("llm_model_name"):
                    self.llm_model_name = data["llm_model_name"]
        except (json.JSONDecodeError, OSError):
            pass

    def _save(self) -> None:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if self.llm_api_key:
            data["llm_api_key"] = self.llm_api_key
        if self.llm_base_url:
            data["llm_base_url"] = self.llm_base_url
        if self.llm_model_name:
            data["llm_model_name"] = self.llm_model_name
        CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def update(self, **kwargs) -> None:
        for key in ("llm_api_key", "llm_base_url", "llm_model_name"):
            if key in kwargs and kwargs[key]:
                setattr(self, key, kwargs[key])
        self._save()

    def to_dict(self) -> dict:
        return {
            "llm_api_key": "***" if self.llm_api_key else "",
            "llm_base_url": self.llm_base_url or "",
            "llm_model_name": self.llm_model_name or "",
        }

    @property
    def is_configured(self) -> bool:
        return bool(self.llm_api_key and self.llm_model_name)


runtime_config = RuntimeConfigStore()
