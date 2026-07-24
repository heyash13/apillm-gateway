import time
from apillm.config import config

class ApillmAuth:
    def __init__(self):
        self.rate_limit_enabled = config.get("rate_limiting", "enabled", True)
        self.default_rpm = config.get("rate_limiting", "requests_per_minute", 60)
        
        # Load API keys from config
        self.keys = {}
        self.load_keys()
        
        # In-memory tracking of request timestamps for rate limiting: key -> list of floats (timestamps)
        self.request_history = {}

    def load_keys(self):
        access_keys = config.get("access_keys", default=[])
        self.keys = {}
        for item in access_keys:
            key_val = item.get("key")
            if key_val:
                self.keys[key_val] = {
                    "description": item.get("description", ""),
                    "rate_limit": item.get("rate_limit_override", self.default_rpm)
                }

    def validate_key(self, api_key: str) -> bool:
        if not api_key:
            return False
        return api_key in self.keys

    def is_rate_limited(self, api_key: str) -> tuple[bool, int]:
        """
        Checks if the api_key has exceeded its rate limit.
        Returns: (is_limited, requests_allowed_in_window)
        """
        if not self.rate_limit_enabled:
            return False, 999999

        key_info = self.keys.get(api_key)
        if not key_info:
            return True, 0 # Invalid key is limited to 0

        limit = key_info["rate_limit"]
        now = time.time()
        
        if api_key not in self.request_history:
            self.request_history[api_key] = []
            
        # Filter timestamps to last 60 seconds
        cutoff = now - 60.0
        self.request_history[api_key] = [t for t in self.request_history[api_key] if t > cutoff]
        
        history = self.request_history[api_key]
        if len(history) >= limit:
            return True, limit - len(history)
            
        # Log this request timestamp
        self.request_history[api_key].append(now)
        return False, limit - len(history)

# Global auth instance
auth = ApillmAuth()
