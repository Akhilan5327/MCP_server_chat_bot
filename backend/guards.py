"""
Price guard: the model may only state rupee amounts that a tool actually returned.

apply_price_guard(reply, messages) looks at every "INR 250", "Rs 250" or rupee-sign
amount in the reply and checks it against the money fields (price, total, ...) in the tool results
of the conversation. Counts such as pages or copies never count. If any amount is unsupported, the reply is replaced with a safe
message that sends the customer to the shop.
"""
import json
import re

AMOUNT_RE = re.compile(r"(?:INR|Rs\.?|₹)\s*([0-9][0-9,]*(?:\.[0-9]+)?)", re.IGNORECASE)

SAFE_REPLY = (
    "Sorry, I could not confirm that price. "
    "Please contact or visit the shop for the exact charge."
)


# Amounts written as data instead of with a currency marker, for example
# {"price": 350} or total = 350, must be checked too.
FIELD_AMOUNT_RE = re.compile(
    r"""["']?(?:price|total|cost|amount|fee|charge|rate)[a-z_]*["']?\s*[:=]\s*["']?([0-9][0-9,]*(?:\.[0-9]+)?)""",
    re.IGNORECASE,
)


def _to_float(text: str) -> float:
    return round(float(text.replace(",", "")), 2)


# Only numbers stored under these field names are rupee amounts. Counts and
# percentages (pages, copies, total_pages, discount_pct) must never support a price.
MONEY_KEYS = {"price", "price_per_page", "min_charge", "base_cost",
              "discount_amount", "total", "cost"}


def _money_in_json(value, found: set, key=None):
    """Collect numbers stored under money fields in parsed JSON.

    Strings are scanned only for amounts written with a currency marker
    ("INR 20", "Rs 20", rupee sign), so text such as "call 250 times" supports nothing.
    """
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        if key in MONEY_KEYS:
            found.add(round(float(value), 2))
    elif isinstance(value, str):
        for token in AMOUNT_RE.findall(value):
            found.add(_to_float(token))
    elif isinstance(value, dict):
        for k, v in value.items():
            _money_in_json(v, found, k)
    elif isinstance(value, list):
        for v in value:
            _money_in_json(v, found, key)


def _json_blocks(content: str):
    """Yield every JSON value in text, even when several blocks are joined together."""
    decoder = json.JSONDecoder()
    i, n = 0, len(content)
    while i < n:
        if content[i] in "{[":
            try:
                value, end = decoder.raw_decode(content, i)
            except ValueError:
                i += 1
                continue
            yield value
            i = end
        else:
            i += 1


def tool_numbers(messages) -> set:
    """All rupee amounts that appear in tool results anywhere in the conversation."""
    allowed = set()
    for m in messages:
        if m.get("role") != "tool":
            continue
        content = m.get("content") or ""
        if not isinstance(content, str):
            content = json.dumps(content)
        _money_in_json(content, allowed)  # currency-marked amounts in any raw text
        for block in _json_blocks(content):
            _money_in_json(block, allowed)
    return allowed


def find_unsupported_prices(reply: str, messages) -> list:
    """Return the rupee amounts in `reply` that no tool result contains."""
    allowed = tool_numbers(messages)
    bad = []
    tokens = AMOUNT_RE.findall(reply or "") + FIELD_AMOUNT_RE.findall(reply or "")
    for token in tokens:
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