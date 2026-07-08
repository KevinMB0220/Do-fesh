import yaml
from pathlib import Path
from typing import Dict, List, Any

class ConfigLoader:
    def __init__(self, base_dir: Path = None):
        if base_dir is None:
            # Resolve relative to this module: secopsentinel/config.py -> parent -> parent -> config
            self.base_dir = Path(__file__).parent.parent
        else:
            self.base_dir = Path(base_dir)
            
        self.config_dir = self.base_dir / "config"
        self.datasets = self._load_yaml(self.config_dir / "datasets.yaml")
        self.rules_config = self._load_yaml(self.config_dir / "rules.yaml")

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def get_safe_fields(self) -> List[str]:
        return self.datasets.get("safe_fields", [])

    def get_dataset_metadata(self) -> Dict[str, Any]:
        return self.datasets.get("dataset", {})

    def get_rules(self) -> List[Dict[str, Any]]:
        return self.rules_config.get("rules", [])
