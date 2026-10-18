import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from guards import apply_price_guard

# pretend the lookup tool returned a PAN price of 300
tool_result = {"role": "tool", "content": '{"service": "PAN Card", "price": 300.0}'}

for reply in [
    "PAN card costs INR 300 at our shop.",       # amount came from the tool: allowed
    "PAN card costs INR 350 at our shop.",       # amount the tool never returned: blocked
    "Please contact or visit the shop.",         # no amount at all: allowed
]:
    text, blocked = apply_price_guard(reply, [tool_result])
    print("BLOCKED" if blocked else "ALLOWED", "|", text)