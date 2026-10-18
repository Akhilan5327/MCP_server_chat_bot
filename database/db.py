"""
Read-only data access layer for the Xerox Shop Assistant.

Deliberately uses plain sqlite3 (stdlib, no install needed) rather than
an ORM, since the scope here is a handful of simple read queries.
Every function in this file only ever SELECTs — no INSERT/UPDATE/DELETE.
"""
import re
import sqlite3
import os
import datetime
from zoneinfo import ZoneInfo

DB_PATH = os.path.join(os.path.dirname(__file__), "shop.db")
INDIA_TZ = ZoneInfo("Asia/Kolkata")

CONTACT_MESSAGE = (
    "The shop does offer this service, but there is no fixed price because it "
    "depends on the case. Tell the customer to contact or visit the shop for "
    "more information. Do not mention any price."
)
NOT_LISTED_MESSAGE = (
    "This service is not in the shop's list. Tell the customer you do not have "
    "it listed and ask them to contact or visit the shop to check."
)


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_services():
    """Return all services with descriptions, grouped implicitly by category."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT name, description, category FROM services ORDER BY category, name"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_shop_hours(day: str = None):
    """
    day: 'today', 'tomorrow', or a weekday name like 'Monday'. Defaults to 'today'.
    Returns open/close times, closed status, and whether it's a holiday.
    """
    target_date = _resolve_date(day)
    weekday_index = target_date.weekday()  # 0=Monday

    conn = _connect()
    try:
        holiday = conn.execute(
            "SELECT description FROM holidays WHERE date = ?",
            (target_date.isoformat(),),
        ).fetchone()
        if holiday:
            return {
                "date": target_date.isoformat(),
                "is_closed": True,
                "reason": f"Holiday: {holiday['description']}",
            }

        row = conn.execute(
            "SELECT open_time, close_time, is_closed FROM shop_hours WHERE day_of_week = ?",
            (weekday_index,),
        ).fetchone()
        if not row or row["is_closed"]:
            return {"date": target_date.isoformat(), "is_closed": True, "reason": "Regular weekly off"}

        return {
            "date": target_date.isoformat(),
            "is_closed": False,
            "open_time": row["open_time"],
            "close_time": row["close_time"],
        }
    finally:
        conn.close()


def is_open_now():
    """Check whether the shop is open using the current Asia/Kolkata time."""

    now = datetime.datetime.now(INDIA_TZ)

    hours = get_shop_hours("today")

    if hours["is_closed"]:
        return {
            "open_now": False,
            "reason": hours.get("reason", "Closed today"),
            "current_time": now.strftime("%H:%M"),
            "timezone": "Asia/Kolkata",
        }

    current_time = now.strftime("%H:%M")

    if hours["open_time"] <= current_time < hours["close_time"]:
        return {
            "open_now": True,
            "current_time": current_time,
            "opens_at": hours["open_time"],
            "closes_at": hours["close_time"],
            "timezone": "Asia/Kolkata",
        }

    return {
        "open_now": False,
        "current_time": current_time,
        "opens_at": hours["open_time"],
        "closes_at": hours["close_time"],
        "timezone": "Asia/Kolkata",
    }


def get_print_price(service_name: str, color_mode: str, paper_size: str = "A4"):
    """Look up the per-page price for a given service/color/paper size combination."""
    conn = _connect()
    try:
        row = conn.execute(
            """SELECT p.price_per_page, p.min_charge
               FROM pricing p JOIN services s ON s.id = p.service_id
               WHERE LOWER(s.name) = LOWER(?) AND LOWER(p.color_mode) = LOWER(?)
                 AND LOWER(p.paper_size) = LOWER(?)""",
            (service_name, color_mode, paper_size),
        ).fetchone()
        if not row:
            return {"found": False, "message": f"No pricing found for {service_name} / {color_mode} / {paper_size}"}
        return {"found": True, "price_per_page": row["price_per_page"], "min_charge": row["min_charge"]}
    finally:
        conn.close()

_ALIASES = {
    "aadhaar": "aadhar", "adhaar": "aadhar", "licence": "license",
    "tirupathi": "tirupati", "dharshan": "darshan",
    "sabarimalai": "sabarimala", "sabarilmalai": "sabarimala",
    "pancard": "pan card", "voterid": "voter id", "smartcard": "smart card",
    "aadharcard": "aadhar card",
}


_GENERIC_WORDS = {
    "new", "apply", "application", "correction", "change", "update", "edit",
    "name", "address", "mobile", "phone", "number", "renewal", "renew",
    "fee", "price", "cost", "charge", "for", "the", "a", "of", "to", "my",
    "how", "much", "what", "is", "in",
}
# words that point to an option of a fixed-price service
_OPTION_HINTS = {
    "correction": {"change", "update", "edit", "name", "address", "mobile", "phone", "number", "correct", "fix"},
    "new application": {"new", "apply", "fresh"},
}


def _with_contact(conn, message: str) -> str:
    """Add the shop's contact details (from the FAQ table) to a 'contact the shop' message."""
    row = conn.execute("SELECT answer FROM faq WHERE category = 'contact' LIMIT 1").fetchone()
    return f"{message} Shop contact: {row['answer']}" if row else message


def _norm(text: str) -> str:
    """Lowercase, fix common spellings, drop punctuation."""
    text = (text or "").lower()
    for wrong, right in _ALIASES.items():
        text = text.replace(wrong, right)
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", text).split())


def _find_services(conn, query: str):
    """Forgiving lookup; if one name just extends another, prefer the shorter."""
    hits = _find_services_raw(conn, query)
    if len(hits) > 1:
        names = {h['id']: _norm(h['name']) for h in hits}
        keep = [h for h in hits if not any(
            o != h['id'] and names[h['id']].startswith(names[o] + ' ') for o in names)]
        hits = keep or hits
    return hits


def _find_services_raw(conn, query: str):
    q = _norm(query)
    if len(q) < 2:
        return []
    rows = conn.execute("SELECT id, name, description FROM services").fetchall()
    named = [(r, _norm(r["name"])) for r in rows]

    # 1. exact name
    hit = [r for r, n in named if n == q]
    if hit:
        return hit
    # 2. query inside name
    hit = [r for r, n in named if q in n]
    if hit:
        return hit
    # 3. name inside query (longest name wins)
    hit = [(r, n) for r, n in named if len(n) >= 4 and n in q]
    if hit:
        best = max(len(n) for _, n in hit)
        return [r for r, n in hit if len(n) == best]
    # 3b. drop generic words (correction, new, ...) and retry on what is left
    rest = " ".join(w for w in q.split() if w not in _GENERIC_WORDS)
    if rest and rest != q:
        found = _find_services_raw(conn, rest)
        if found:
            return found
    # 4. query matches a fixed-price option name
    opt = conn.execute(
        """SELECT DISTINCT s.id, s.name, s.description FROM service_pricing sp
           JOIN services s ON s.id = sp.service_id"""
    ).fetchall()
    opts = conn.execute("SELECT service_id, service_option FROM service_pricing").fetchall()
    ids = {o["service_id"] for o in opts if _norm(o["service_option"]) and _norm(o["service_option"]) in q or q in _norm(o["service_option"])}
    hit = [r for r in opt if r["id"] in ids]
    if hit:
        return hit
    # 5. every word appears in name + description
    words = q.split()
    return [r for r in rows if all(w in _norm(r["name"] + " " + (r["description"] or "")) for w in words)]


def _describe_service(conn, service):
    rows = conn.execute(
        "SELECT service_option, price FROM service_pricing WHERE service_id = ? ORDER BY id",
        (service["id"],),
    ).fetchall()
    if rows:
        return {"service": service["name"], "fixed_price": True,
                "options": [dict(r) for r in rows]}
    per_page = conn.execute(
        "SELECT 1 FROM pricing WHERE service_id = ? LIMIT 1", (service["id"],)
    ).fetchone()
    if per_page:
        return {"service": service["name"], "fixed_price": False,
                "message": "This service is priced per page. Use calculate_order_price."}
    return {"service": service["name"], "fixed_price": False,
            "message": _with_contact(conn, CONTACT_MESSAGE)}


def get_service_options(service_name: str):
    """Look up how any shop service is priced (fixed price, per page, or contact the shop)."""
    conn = _connect()
    try:
        matches = _find_services(conn, service_name)
        if not matches:
            return {"found": False, "message": _with_contact(conn, NOT_LISTED_MESSAGE)}
        if len(matches) == 1:
            return {"found": True, **_describe_service(conn, matches[0])}
        return {"found": True, "multiple_matches": True,
                "services": [_describe_service(conn, m) for m in matches]}
    finally:
        conn.close()


def get_service_price(service_name: str, service_option: str):
    """Look up the fixed price for one option of a service."""
    info = get_service_options(service_name)
    if not info.get("found") or info.get("multiple_matches") or not info.get("fixed_price"):
        return info
    want = _norm(service_option)
    opts = info["options"]
    pick = [o for o in opts if _norm(o["service_option"]) == want] or \
           [o for o in opts if want and (want in _norm(o["service_option"]) or _norm(o["service_option"]) in want)]
    if not pick:
        words = set(want.split())
        for o in opts:
            hints = _OPTION_HINTS.get(_norm(o["service_option"]), set())
            if words & hints:
                pick.append(o)
    if len(pick) == 1:
        return {"found": True, "service": info["service"],
                "option": pick[0]["service_option"], "price": pick[0]["price"]}
    return {"found": False,
            "message": f"No price listed for {info['service']} / {service_option}. "
                       "Tell the customer to contact or visit the shop.",
            "options": opts}


def calculate_order_price(
    service_name: str,
    pages: int,
    color_mode: str,
    paper_size: str = "A4",
    copies: int = 1,
    add_on_names: list = None,
):
    """
    Full itemized quote: base cost, bulk discount if applicable, add-ons, and total.
    Pure calculation over read-only tables — creates nothing.
    """
    add_on_names = add_on_names or []
    price_info = get_print_price(service_name, color_mode, paper_size)
    if not price_info["found"]:
        return price_info

    total_pages = pages * copies
    base_cost = total_pages * price_info["price_per_page"]
    base_cost = max(base_cost, price_info["min_charge"])

    conn = _connect()
    try:
        # Apply the best-matching discount tier
        tier = conn.execute(
            """SELECT discount_pct FROM discount_tiers
               WHERE min_pages <= ? ORDER BY min_pages DESC LIMIT 1""",
            (total_pages,),
        ).fetchone()
        discount_pct = tier["discount_pct"] if tier else 0.0
        discount_amount = base_cost * (discount_pct / 100)

        # Add-ons
        add_on_lines = []
        add_on_total = 0.0
        for name in add_on_names:
            row = conn.execute(
                "SELECT name, price, unit FROM add_ons WHERE LOWER(name) = LOWER(?)",
                (name,),
            ).fetchone()
            if row:
                cost = row["price"] * total_pages if row["unit"] == "per_page" else row["price"]
                add_on_lines.append({"name": row["name"], "cost": round(cost, 2)})
                add_on_total += cost
            else:
                add_on_lines.append({"name": name, "cost": None, "note": "add-on not found"})

        subtotal = base_cost - discount_amount + add_on_total
        return {
            "found": True,
            "service": service_name,
            "pages": pages,
            "copies": copies,
            "total_pages": total_pages,
            "color_mode": color_mode,
            "paper_size": paper_size,
            "price_per_page": price_info["price_per_page"],
            "base_cost": round(base_cost, 2),
            "discount_pct": discount_pct,
            "discount_amount": round(discount_amount, 2),
            "add_ons": add_on_lines,
            "total": round(subtotal, 2),
        }
    finally:
        conn.close()


_FAQ_STOP = {"the", "what", "how", "can", "you", "your", "shop", "is", "are", "for", "and",
             "does", "do", "give", "tell", "please", "any", "has", "have", "with", "about"}
_FAQ_SYNONYMS = {
    "address": "location", "where": "location", "map": "location", "maps": "location",
    "directions": "location", "located": "location", "landmark": "location",
    "phone": "contact", "mobile": "contact", "number": "contact", "call": "contact",
    "whatsapp": "contact", "reach": "contact",
}


def get_faq_info(query: str):
    """FAQ search. Tries the whole phrase first, then falls back to the best word matches."""
    conn = _connect()
    try:
        like = f"%{query}%"
        rows = conn.execute(
            """SELECT question, answer, category FROM faq
               WHERE question LIKE ? OR answer LIKE ? OR category LIKE ?""",
            (like, like, like),
        ).fetchall()
        if rows:
            return [dict(r) for r in rows]

        words = set()
        for w in re.findall(r"[a-z0-9]+", (query or "").lower()):
            if len(w) >= 3 and w not in _FAQ_STOP:
                words.add(w)
                if w in _FAQ_SYNONYMS:
                    words.add(_FAQ_SYNONYMS[w])
        if not words:
            return []
        scored = []
        for r in conn.execute("SELECT question, answer, category FROM faq").fetchall():
            text = f"{r['question']} {r['answer']} {r['category']}".lower()
            score = sum(1 for w in words if w in text)
            if score:
                scored.append((score, dict(r)))
        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:5]]
    finally:
        conn.close()


def _resolve_date(day: str = None) -> datetime.date:
    today = datetime.datetime.now(INDIA_TZ).date()
    if not day or day.lower() == "today":
        return today
    if day.lower() == "tomorrow":
        return today + datetime.timedelta(days=1)

    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    day_lower = day.lower()
    if day_lower in weekdays:
        target_idx = weekdays.index(day_lower)
        delta = (target_idx - today.weekday()) % 7
        return today + datetime.timedelta(days=delta)

    # Fallback: assume ISO date string 'YYYY-MM-DD'
    try:
        return datetime.date.fromisoformat(day)
    except ValueError:
        return today