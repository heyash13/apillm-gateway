import sqlite3
import hashlib
import json
import time
import os
from apillm.config import config

class ApillmCache:
    def __init__(self):
        self.enabled = config.get("caching", "enabled", True)
        self.ttl = config.get("caching", "ttl_seconds", 3600)
        
        # Determine DB path relative to the config.json directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_name = config.get("caching", "database_path", "apillm_cache.db")
        self.db_path = os.path.join(base_dir, db_name)
        
        if self.enabled:
            self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prompt_cache (
                prompt_hash TEXT PRIMARY KEY,
                prompt TEXT,
                response_data TEXT,
                created_at INTEGER,
                billing_cost REAL,
                tokens_used INTEGER
            )
        """)
        conn.commit()
        conn.close()

    def _hash_prompt(self, prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    def get(self, prompt: str) -> dict | None:
        if not self.enabled:
            return None
            
        prompt_hash = self._hash_prompt(prompt)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT response_data, created_at FROM prompt_cache WHERE prompt_hash = ?", 
            (prompt_hash,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            response_json_str, created_at = row
            now = int(time.time())
            
            # Check TTL
            if now - created_at > self.ttl:
                # Cache expired, delete it
                self.delete(prompt)
                return None
                
            try:
                return json.loads(response_json_str)
            except Exception:
                return None
        return None

    def set(self, prompt: str, response_data: dict, tokens_used: int = 0, billing_cost: float = 0.0):
        if not self.enabled:
            return
            
        prompt_hash = self._hash_prompt(prompt)
        response_json_str = json.dumps(response_data)
        now = int(time.time())
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO prompt_cache (prompt_hash, prompt, response_data, created_at, billing_cost, tokens_used)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (prompt_hash, prompt, response_json_str, now, billing_cost, tokens_used))
            conn.commit()
        except Exception as e:
            print(f"[Apillm Cache Error] Failed to write cache: {e}")
        finally:
            conn.close()

    def delete(self, prompt: str):
        prompt_hash = self._hash_prompt(prompt)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM prompt_cache WHERE prompt_hash = ?", (prompt_hash,))
        conn.commit()
        conn.close()

    def clear(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM prompt_cache")
        conn.commit()
        conn.close()

# Global cache instance
cache = ApillmCache()
