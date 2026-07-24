import json
import os
import time
import threading

class ApillmLogger:
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.log_path = os.path.join(base_dir, "apillm_audit.jsonl")
        self.stats_path = os.path.join(base_dir, "apillm_stats.json")
        self.lock = threading.Lock()
        
        # Load or initialize running stats
        self.stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_cost_saved": 0.0,
            "total_cost_spent": 0.0,
            "total_tokens_saved": 0,
            "total_tokens_spent": 0,
            "pii_redacted_count": 0,
            "start_time": int(time.time())
        }
        self._load_stats()

    def _load_stats(self):
        if os.path.exists(self.stats_path):
            try:
                with open(self.stats_path, "r") as f:
                    self.stats.update(json.load(f))
            except Exception:
                pass

    def _save_stats(self):
        try:
            with open(self.stats_path, "w") as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            print(f"[Apillm Logger Error] Failed to save stats: {e}")

    def log_request(self, api_key: str, client_ip: str, provider: str, 
                    prompt_len: int, scrubbed_prompt: str, detections: list, 
                    cache_hit: bool, cost: float, tokens: int, status_code: int):
        with self.lock:
            # Update stats
            self.stats["total_requests"] += 1
            if cache_hit:
                self.stats["cache_hits"] += 1
                self.stats["total_cost_saved"] += cost
                self.stats["total_tokens_saved"] += tokens
            else:
                self.stats["cache_misses"] += 1
                self.stats["total_cost_spent"] += cost
                self.stats["total_tokens_spent"] += tokens

            if detections:
                self.stats["pii_redacted_count"] += sum(d["count"] for d in detections)
                
            self._save_stats()
            
            # Prepare log entry (ensure prompt in logs doesn't leak original data)
            # Take a small snippet of scrubbed prompt
            prompt_snippet = scrubbed_prompt[:100] + "..." if len(scrubbed_prompt) > 100 else scrubbed_prompt
            
            entry = {
                "timestamp": int(time.time()),
                "client_ip": client_ip,
                "api_key_desc": "sg-key-***" + api_key[-4:] if len(api_key) > 4 else "unknown",
                "provider": provider,
                "prompt_length": prompt_len,
                "prompt_snippet": prompt_snippet,
                "detections": detections,
                "cache_hit": cache_hit,
                "cost": cost,
                "tokens": tokens,
                "status_code": status_code
            }
            
            # Write to audit file
            try:
                with open(self.log_path, "a") as f:
                    f.write(json.dumps(entry) + "\n")
            except Exception as e:
                print(f"[Apillm Logger Error] Failed to write log: {e}")

    def get_recent_logs(self, limit=20) -> list:
        if not os.path.exists(self.log_path):
            return []
        
        logs = []
        with self.lock:
            try:
                with open(self.log_path, "r") as f:
                    for line in f:
                        if line.strip():
                            logs.append(json.loads(line))
            except Exception:
                pass
        # Return last N logs in reverse chronological order
        return list(reversed(logs[-limit:]))

    def get_stats(self) -> dict:
        with self.lock:
            return self.stats.copy()

# Global logger instance
logger = ApillmLogger()
