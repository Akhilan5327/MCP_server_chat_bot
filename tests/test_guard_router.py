"""
Tests for the price guard and the model router. No network needed.
Run:  python -m pytest tests -v
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from guards import SAFE_REPLY, apply_price_guard, find_unsupported_prices  # noqa: E402
from llm_router import ModelRouter  # noqa: E402

import pytest  # noqa: E402


def tool_msg(text):
    return {"role": "tool", "content": text}


# ---------------- price guard ----------------
def test_guard_allows_price_from_tool():
    msgs = [tool_msg('{"found": true, "options": [{"service_option": "Correction", "price": 250.0}]}')]
    reply, blocked = apply_price_guard("Aadhar correction costs INR 250.", msgs)
    assert blocked is False and reply.startswith("Aadhar")


def test_guard_blocks_invented_price():
    msgs = [tool_msg('{"found": true, "options": [{"service_option": "Correction", "price": 250.0}]}')]
    reply, blocked = apply_price_guard("It costs INR 300.", msgs)
    assert blocked is True and reply == SAFE_REPLY


def test_guard_blocks_price_with_no_tool_call():
    reply, blocked = apply_price_guard("A train ticket costs INR 50.", [])
    assert blocked is True


def test_guard_ignores_replies_without_prices():
    reply, blocked = apply_price_guard("Please contact or visit the shop.", [])
    assert blocked is False


def test_guard_handles_commas_decimals_and_symbols():
    msgs = [tool_msg('{"total": 1250.5}')]
    assert find_unsupported_prices("Total INR 1,250.50", msgs) == []
    assert find_unsupported_prices("Total Rs. 1250.5", msgs) == []
    assert find_unsupported_prices("Total ₹999", msgs) == [999.0]


def test_guard_ignores_numbers_inside_strings_of_tool_results():
    msgs = [tool_msg('{"message": "call 250 times", "price": 100}')]
    assert find_unsupported_prices("INR 250", msgs) == [250.0]


def test_guard_handles_non_json_tool_output():
    msgs = [tool_msg('{"price": 100}\n{"price": 200}')]
    assert find_unsupported_prices("INR 100 and INR 200", msgs) == []


def test_guard_multiple_amounts_one_bad():
    msgs = [tool_msg('{"price": 100}')]
    assert find_unsupported_prices("INR 100 or INR 120", msgs) == [120.0]


# ---------------- model router ----------------
class FakeError(Exception):
    def __init__(self, status_code, retry_after=None):
        super().__init__(f"error {status_code}")
        self.status_code = status_code
        self.response = type("R", (), {"headers": {"retry-after": retry_after} if retry_after else {}})()


class FakeClient:
    """Fails for models listed in `fail`, otherwise returns the model name."""
    def __init__(self, fail):
        self.fail = fail
        self.calls = []
        outer = self
        class Completions:
            def create(self, model, messages, tools):
                outer.calls.append(model)
                if model in outer.fail:
                    raise outer.fail[model]
                return model
        self.chat = type("Chat", (), {"completions": Completions()})()


CHAINS = {"simple": ["small", "mid", "big"], "hard": ["big", "mid", "small"]}


def run(coro):
    return asyncio.run(coro)


def test_router_uses_first_model_when_healthy():
    client = FakeClient({})
    r = ModelRouter(client, CHAINS)
    out = run(r.create([], ["small", "mid"], "sys", []))
    assert out == "small" and client.calls == ["small"]


def test_router_fails_over_on_rate_limit():
    client = FakeClient({"small": FakeError(429)})
    r = ModelRouter(client, CHAINS)
    out = run(r.create([], ["small", "mid", "big"], "sys", []))
    assert out == "mid"
    assert r.stats["fallbacks"] == 1 and r.stats["rate_limited"] == 1


def test_router_skips_cooling_model_next_time():
    client = FakeClient({"small": FakeError(429, retry_after="20")})
    r = ModelRouter(client, CHAINS)
    run(r.create([], ["small", "mid"], "sys", []))
    client.calls.clear()
    run(r.create([], ["small", "mid"], "sys", []))
    assert client.calls == ["mid"]  # small was not even tried


def test_router_fails_over_on_server_error_and_bad_request():
    client = FakeClient({"small": FakeError(503), "mid": FakeError(400)})
    r = ModelRouter(client, CHAINS)
    assert run(r.create([], ["small", "mid", "big"], "sys", [])) == "big"


def test_router_raises_when_all_fail():
    client = FakeClient({m: FakeError(429) for m in ["small", "mid"]})
    r = ModelRouter(client, CHAINS)
    with pytest.raises(FakeError):
        run(r.create([], ["small", "mid"], "sys", []))
    assert r.stats["failed"] == 1


def test_router_retries_cooling_models_once_before_giving_up():
    client = FakeClient({})
    r = ModelRouter(client, CHAINS)
    import time
    r._cooldown["small"] = time.monotonic() + 100
    r._cooldown["mid"] = time.monotonic() + 100
    assert run(r.create([], ["small", "mid"], "sys", [])) == "small"


def test_pick_chain_routes_hard_questions_to_big_model():
    r = ModelRouter(FakeClient({}), CHAINS)
    assert r.pick_chain("aadhar price", [])[0] == "small"
    assert r.pick_chain("ஆதார் விலை என்ன", [])[0] == "big"
    assert r.pick_chain("x" * 200, [])[0] == "big"
    assert r.pick_chain("price", [{}] * 9)[0] == "big"