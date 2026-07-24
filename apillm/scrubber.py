import re
from apillm.config import config

class ApillmScrubber:
    def __init__(self):
        self.rules = []
        self.replacement_template = config.get("security", "redact_replacement", "[REDACTED_{rule_name}]")
        self.enabled = config.get("security", "redaction_enabled", True)
        self.load_rules()

    def load_rules(self):
        config_rules = config.get("security", "rules", [])
        self.rules = []
        for r in config_rules:
            if r.get("enabled", True):
                try:
                    compiled = re.compile(r["pattern"])
                    self.rules.append({
                        "name": r["name"],
                        "regex": compiled
                    })
                except Exception as e:
                    print(f"[Apillm Config Error] Failed to compile regex for rule '{r.get('name')}': {e}")

    def scrub(self, text: str) -> tuple[str, list[dict]]:
        if not self.enabled or not text:
            return text, []

        detections = []
        scrubbed = text
        
        for rule in self.rules:
            matches = rule["regex"].findall(scrubbed)
            if matches:
                replacement = self.replacement_template.format(rule_name=rule["name"])
                scrubbed = rule["regex"].sub(replacement, scrubbed)
                detections.append({
                    "rule": rule["name"],
                    "count": len(matches)
                })
                
        return scrubbed, detections

# Global scrubber instance
scrubber = ApillmScrubber()
