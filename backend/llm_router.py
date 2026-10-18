"""
Model routing and automatic failover for Groq.

- pick_chain() chooses an ordered list of models for a message.
- create() tries them in order. On a rate limit (429) or a server error it moves to
  the next model straight away, and remembers (cooldown) that the model is busy so
  later requests skip it instead of waiting.

Create the Groq client with max_retries=0, otherwise the SDK sleeps and retries
by itself before this code ever sees the error.
"""
import asyncio
import logging
import re
import time

logger = logging.getLogger("shop_agent")

TAMIL_RE = re.compile(r"[஀-௿]")


class ModelRouter:
    def __init__(self, client, chains: dict, long_message_chars: int = 150, long_history: int = 8):
        self.client = client
        self.chains = chains
        self.long_message_chars = long_message_chars
        self.long_history = long_history
        self._cooldown = {}  # model -> time.monotonic() until which it is skipped
        self.stats = {"calls": 0, "fallbacks": 0, "rate_limited": 0, "failed": 0}

    def pick_chain(self, message: str, history: list) -> list:
        """Harder messages go to the bigger model first."""
        hard = (
            bool(TAMIL_RE.search(message))
            or len(message) > self.long_message_chars
            or len(history) > self.long_history
        )
        return list(self.chains["hard" if hard else "simple"])

    def _set_cooldown(self, model: str, error: Exception):
        status = getattr(error, "status_code", None)
        seconds = 0
        if status == 429:
            self.stats["rate_limited"] += 1
            seconds = 30
            headers = getattr(getattr(error, "response", None), "headers", None)
            try:
                seconds = min(float(headers.get("retry-after")), 120) if headers else 30
            except (TypeError, ValueError):
                seconds = 30
        elif status == 404 or (isinstance(status, int) and status >= 500):
            seconds = 60
        if seconds:
            self._cooldown[model] = time.monotonic() + seconds

    async def _try_models(self, models, messages, system_prompt, tools):
        last_error = None
        for model in models:
            try:
                self.stats["calls"] += 1
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=model,
                    messages=[{"role": "system", "content": system_prompt}] + messages,
                    tools=tools,
                )
                return model, response, None
            except Exception as e:  # rate limit, server error, bad tool call...
                last_error = e
                self._set_cooldown(model, e)
                logger.warning("Model %s failed (%s): %s", model, getattr(e, "status_code", "no status"), e)
        return None, None, last_error

    async def create(self, messages, chain, system_prompt, tools):
        now = time.monotonic()
        available = [m for m in chain if self._cooldown.get(m, 0) <= now]

        model, response, error = await self._try_models(available, messages, system_prompt, tools)
        if response is None and len(available) < len(chain):
            # everything left failed or was cooling down: try the skipped ones once
            skipped = [m for m in chain if m not in available]
            model, response, error = await self._try_models(skipped, messages, system_prompt, tools)

        if response is None:
            self.stats["failed"] += 1
            raise error or RuntimeError("No model available")

        if model != chain[0]:
            self.stats["fallbacks"] += 1
            logger.warning("FALLBACK: used %s instead of %s", model, chain[0])
        return response