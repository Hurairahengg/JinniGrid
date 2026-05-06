"""
JINNI Grid - Configuration Loader
Reads config.yaml from project root. Falls back to safe defaults.
app/config.py
"""
import os, yaml

_config_cache = None

_DEFAULTS = {
    "server": {"host": "0.0.0.0", "port": 5100, "debug": False, "cors_origins": ["*"]},
    "app": {"name": "JINNI Grid Mother Server", "version": "0.2.0"},
    "fleet": {"stale_threshold_seconds": 30, "offline_threshold_seconds": 90},
}


def _load_config() -> dict:
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    config_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(config_dir)
    config_path = os.path.join(project_root, "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            _config_cache = yaml.safe_load(f)
        print(f"[CONFIG] Loaded config from: {config_path}")
    else:
        print(f"[CONFIG] WARNING: config.yaml not found at {config_path}")
        print("[CONFIG] Using fallback defaults.")
        _config_cache = _DEFAULTS
    return _config_cache


class Config:
    @classmethod
    def get_server_config(cls) -> dict:
        return _load_config().get("server", _DEFAULTS["server"])

    @classmethod
    def get_app_config(cls) -> dict:
        return _load_config().get("app", _DEFAULTS["app"])

    @classmethod
    def get_cors_origins(cls) -> list:
        return cls.get_server_config().get("cors_origins", ["*"])

    @classmethod
    def get_fleet_config(cls) -> dict:
        return _load_config().get("fleet", _DEFAULTS["fleet"])
