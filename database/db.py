"""
Read-only data access layer for the Xerox Shop Assistant.

Deliberately uses plain sqlite3 (stdlib, no install needed) rather than
an ORM, since the scope here is a handful of simple read queries.
Every function in this file only ever SELECTs — no INSERT/UPDATE/DELETE.
"""
import sqlite3
import os
import datetime
from zoneinfo import ZoneInfo

DB_PATH = os.path.join(os.path.dirname(__file__), "shop.db")
INDIA_TZ = ZoneInfo("Asia/Kolkata")


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

def get_service_price(service_name: str, service_option: str):
    """Look up the fixed price for a non-printing service."""
    conn = _connect()
    try:
        row = conn.execute(
            """SELECT s.name, sp.service_option, sp.price
               FROM service_pricing sp
               JOIN services s ON s.id = sp.service_id
               WHERE LOWER(s.name) = LOWER(?)
                 AND LOWER(sp.service_option) = LOWER(?)""",
            (service_name, service_option),
        ).fetchone()

        if not row:
            return {
                "found": False,
                "message": f"No pricing found for {service_name} / {service_option}",
            }

        return {
            "found": True,
            "service": row["name"],
            "option": row["service_option"],
            "price": row["price"],
        }
    finally:
        conn.close()

def get_service_options(service_name: str):
    """List all valid pricing options and prices for a fixed-fee service."""
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT sp.service_option, sp.price
               FROM service_pricing sp
               JOIN services s ON s.id = sp.service_id
               WHERE LOWER(s.name) = LOWER(?)""",
            (service_name,),
        ).fetchall()
        if not rows:
            return {"found": False, "message": f"No service options found for {service_name}"}
        return {"found": True, "service": service_name, "options": [dict(r) for r in rows]}
    finally:
        conn.close()


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


def get_faq_info(query: str):
    """Simple keyword search over the FAQ table (no fuzzy matching — keep MVP simple)."""
    conn = _connect()
    try:
        like = f"%{query}%"
        rows = conn.execute(
            """SELECT question, answer, category FROM faq
               WHERE question LIKE ? OR answer LIKE ? OR category LIKE ?""",
            (like, like, like),
        ).fetchall()
        return [dict(r) for r in rows]
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
