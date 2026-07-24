import os
import json

class ApillmConfig:
    def __init__(self, config_path=None):
        if not config_path:
            # Look in parent directory of this module
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config.json")
            
        self.config_path = config_path
        self.config_data = {}
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                self.config_data = json.load(f)
        else:
            # Minimal defaults if not found
            self.config_data = {
                "proxy": {"host": "127.0.0.1", "port": 8090, "dashboard_enabled": True},
                "upstream": {
                    "default_provider": "mock-api",
                    "providers": {
                        "mock-api": {"url": "http://127.0.0.1:8095/v1/chat/completions", "api_key": "mock-key-123"}
                    }
                },
                "caching": {"enabled": True, "type": "sqlite", "database_path": "apillm_cache.db", "ttl_seconds": 3600},
                "security": {"redaction_enabled": True, "redact_replacement": "[REDACTED_{rule_name}]", "rules": []},
                "rate_limiting": {"enabled": False},
                "access_keys": []
            }

    def get(self, section, key=None, default=None):
        section_data = self.config_data.get(section, {})
        if key is None:
            return section_data
        return section_data.get(key, default)

# Global configuration instance
config = ApillmConfig()
