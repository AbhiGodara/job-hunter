"""
Smart rate limiter with exponential backoff, key rotation, and batch processing.
Designed for Groq's free tier (12K TPM per key).
"""

import os
import time
import random
from typing import List, Optional


class RateLimiter:
    """
    Manages Groq API rate limits with:
    - Multiple API key rotation
    - Exponential backoff on 429 errors
    - Batch processing for large job lists
    - Cooldown tracking per key
    """

    def __init__(self):
        self.keys = self._load_keys()
        self.current_key_idx = 0
        self.key_cooldowns = {}  # key_idx -> timestamp when it becomes available
        self.batch_size = 3  # Jobs per batch to stay under TPM

    def _load_keys(self) -> List[str]:
        """Load all available Groq API keys."""
        keys = []
        for name in ["GROQ_API_KEY_1", "GROQ_API_KEY_2", "GROQ_API_KEY_3"]:
            key = os.environ.get(name)
            if key:
                keys.append(key)
        if not keys:
            single = os.environ.get("GROQ_API_KEY")
            if single:
                keys.append(single)
        return keys

    @property
    def num_keys(self) -> int:
        return len(self.keys)

    def get_next_key(self) -> str:
        """Get the next available API key, rotating through all keys."""
        if not self.keys:
            raise ValueError("No API keys configured!")

        now = time.time()

        # Try each key starting from current index
        for _ in range(len(self.keys)):
            idx = self.current_key_idx % len(self.keys)
            cooldown_until = self.key_cooldowns.get(idx, 0)

            if now >= cooldown_until:
                self.current_key_idx = idx + 1
                key = self.keys[idx]
                os.environ["GROQ_API_KEY"] = key
                return key

            self.current_key_idx += 1

        # All keys on cooldown — wait for the one with shortest cooldown
        min_idx = min(self.key_cooldowns, key=self.key_cooldowns.get)
        wait_time = self.key_cooldowns[min_idx] - now
        if wait_time > 0:
            print(f"[RateLimiter] All keys on cooldown. Waiting {wait_time:.0f}s...")
            time.sleep(wait_time + 1)

        idx = min_idx
        self.current_key_idx = idx + 1
        key = self.keys[idx]
        os.environ["GROQ_API_KEY"] = key
        return key

    def mark_key_used(self, key: str, cooldown_seconds: int = 65):
        """Mark a key as used, setting its cooldown period."""
        try:
            idx = self.keys.index(key)
            self.key_cooldowns[idx] = time.time() + cooldown_seconds
        except ValueError:
            pass

    def get_wait_time(self) -> float:
        """Get the minimum wait time until any key is available."""
        if not self.key_cooldowns:
            return 0
        now = time.time()
        min_wait = min(max(0, cd - now) for cd in self.key_cooldowns.values())
        return min_wait

    def split_into_batches(self, items: list, batch_size: int = None) -> list:
        """Split items into batches for rate-limited processing."""
        size = batch_size or self.batch_size
        return [items[i : i + size] for i in range(0, len(items), size)]


def retry_with_backoff(func, max_retries: int = 3, base_delay: float = 15.0):
    """
    Execute a function with exponential backoff on rate limit errors.

    Args:
        func: Callable to execute
        max_retries: Maximum number of retries
        base_delay: Base delay in seconds (doubled each retry)

    Returns:
        Function result
    """
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            error_str = str(e).lower()
            is_rate_limit = "rate_limit" in error_str or "429" in error_str or "rate limit" in error_str

            if is_rate_limit and attempt < max_retries:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 5)
                print(f"[RateLimiter] Rate limited. Retry {attempt+1}/{max_retries} in {delay:.0f}s...")
                time.sleep(delay)
            else:
                raise
