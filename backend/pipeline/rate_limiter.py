"""
Groq API key rotation with exponential backoff.
Supports 1–5 keys. Automatically cycles on rate limit.
"""
import time, logging, itertools
from groq import Groq, RateLimitError
from backend.config import GROQ_API_KEYS, GROQ_RPM_LIMIT, GROQ_COOLDOWN_SEC, MAX_RETRIES, LLM_MODELS

log = logging.getLogger(__name__)

class GroqRotatingClient:
    def __init__(self):
        if not GROQ_API_KEYS:
            raise ValueError("No GROQ_API_KEYS set in .env")
        self.clients = [Groq(api_key=k) for k in GROQ_API_KEYS]
        self.cycle = itertools.cycle(range(len(self.clients)))
        self.current_idx = next(self.cycle)
        self.request_count = 0
        self.window_start = time.time()
        self.model_idx = 0

    @property
    def current_model(self):
        return LLM_MODELS[self.model_idx % len(LLM_MODELS)]

    def _next_client(self):
        self.current_idx = next(self.cycle)
        log.info(f"Rotated to API key #{self.current_idx + 1}")

    def _rate_check(self):
        """Enforce RPM limit locally before even hitting API."""
        elapsed = time.time() - self.window_start
        if elapsed > 60:
            self.request_count = 0
            self.window_start = time.time()
        if self.request_count >= GROQ_RPM_LIMIT:
            wait = 60 - elapsed + 2
            log.info(f"Local RPM limit reached. Waiting {wait:.0f}s")
            time.sleep(max(wait, 2))
            self.request_count = 0
            self.window_start = time.time()

    def chat(self, messages: list, temperature: float = 0.2, max_tokens: int = 2000) -> str:
        """
        Calls Groq with automatic retry + key rotation + model fallback.
        Returns response text or raises after MAX_RETRIES.
        """
        for attempt in range(MAX_RETRIES):
            try:
                self._rate_check()
                client = self.clients[self.current_idx]
                resp = client.chat.completions.create(
                    model=self.current_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                self.request_count += 1
                return resp.choices[0].message.content

            except RateLimitError:
                log.warning(f"Rate limit on key #{self.current_idx + 1}, attempt {attempt + 1}")
                if len(self.clients) > 1:
                    self._next_client()
                else:
                    # Try next model (lighter = fewer tokens = hits limit less)
                    self.model_idx += 1
                    log.info(f"Switching model to: {self.current_model}")
                backoff = GROQ_COOLDOWN_SEC * (2 ** attempt)
                log.info(f"Waiting {backoff}s before retry")
                time.sleep(backoff)

            except Exception as e:
                log.error(f"Groq call failed (attempt {attempt + 1}): {e}")
                if attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(5 * (attempt + 1))

        raise RuntimeError("All Groq retries exhausted")

# Singleton — import this everywhere
groq_client = GroqRotatingClient()