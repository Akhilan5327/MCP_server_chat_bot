"""
Price guard: the model may only state rupee amounts that a tool actually returned.

apply_price_guard(reply, messages) looks at every "INR 250", "Rs 250" or rupee-sign
amount in the reply and checks it against the numbers found in the tool results in
the conversation. If any amount is unsupported, the reply is replaced with a safe
message that sends the customer to the shop.
"""
import json
import re

AMOUNT_RE = re.compile(r"(?:INR|Rs\.?|₹)\s*([0-9][0-9,]*(?:\.[0-9]+)?)", re.IGNORECASE)
NUMBER_RE = re.compile(r"[0-9][0-9,]*(?:\.[0-9]+)?")

SAFE_REPLY = (
    "Sorry, I could not confirm that price. "
    "Please contact or visit the shop for the exact charge."
)


def _to_float(text: str) -> float:
    return round(float(text.replace(",", "")), 2)


def _numbers_in_json(value, found: set):
    """Collect numeric values (not numbers inside strings) from parsed JSON."""
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        found.add(round(float(value), 2))
    elif isinstance(value, dict):
        for v in value.values():
            _numbers_in_json(v, found)
    elif isinstance(value, list):
        for v in value:
            _numbers_in_json(v, found)


def tool_numbers(messages) -> set:
    """All numbers that appear in tool results anywhere in the conversation."""
    allowed = set()
    for m in messages:
        if m.get("role") != "tool":
            continue
        content = m.get("content") or ""
        try:
            _numbers_in_json(json.loads(content), allowed)
        except (ValueError, TypeError):
            # not clean JSON (for example several JSON blocks joined together)
            for token in NUMBER_RE.findall(content):
                allowed.add(_to_float(token))
    return allowed


def find_unsupported_prices(reply: str, messages) -> list:
    """Return the rupee amounts in `reply` that no tool result contains."""
    allowed = tool_numbers(messages)
    bad = []
    for token in AMOUNT_RE.findall(reply or ""):
        amount = _to_float(token)
        if amount not in allowed:
            bad.append(amount)
    return bad


def apply_price_guard(reply: str, messages):
    """Return (reply_to_send, was_blocked)."""
    bad = find_unsupported_prices(reply, messages)
    if bad:
        return SAFE_REPLY, True
    return reply, False