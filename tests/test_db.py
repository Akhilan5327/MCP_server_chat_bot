"""
Automated tests for the database layer. No network, no Groq, runs in about a second.
Run from the project root:   python -m pytest tests -v
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "database"))
import db  # noqa: E402

import pytest  # noqa: E402


# ---------- fixed prices ----------
@pytest.mark.parametrize("service, option, price", [
    ("Aadhar Card", "Correction", 250.0),
    ("PAN Card", "New Application", 300.0),
    ("PAN Card", "Correction", 300.0),
    ("Smart Card", "New Application", 200.0),
    ("Smart Card", "Correction", 200.0),
    ("Passport", "New Application", 500.0),
    ("Passport", "Correction", 500.0),
    ("Voter ID", "New Application", 250.0),
    ("Voter ID", "Correction", 250.0),
    ("Online Certificate", "Income Certificate", 300.0),
    ("Online Certificate", "Community Certificate", 300.0),
    ("Online Certificate", "Residential Certificate", 300.0),
    ("Online College Application", "Application", 300.0),
    ("Employment Registration", "Registration", 100.0),
])
def test_fixed_prices(service, option, price):
    r = db.get_service_price(service, option)
    assert r["found"] is True
    assert r["price"] == price


# ---------- forgiving name matching ----------
@pytest.mark.parametrize("query, expected", [
    ("aadhaar", "Aadhar Card"),
    ("aadhar correction", "Aadhar Card"),
    ("pan card", "PAN Card"),
    ("passport name change", "Passport"),
    ("income certificate", "Online Certificate"),
    ("driving licence renewal", "Driving License"),
    ("tirupathi dharshan", "Tirupati Darshan Booking"),
    ("sabarilmalai", "Sabarimala Booking"),
    ("tnpsc", "Government Job Applications"),
    ("neet", "JEE and NEET Applications"),
    ("flight ticket", "Train, Bus and Flight Ticket Booking"),
    ("Pancard", "PAN Card"),
    ("pancard new application", "PAN Card"),
    ("voterid", "Voter ID"),
    ("smartcard", "Smart Card"),
    ("Aadharcard", "Aadhar Card"),
])
def test_name_matching(query, expected):
    r = db.get_service_options(query)
    assert r["found"] is True
    assert r["service"] == expected


# ---------- contact-only services never show a price ----------
CONTACT_ONLY = [
    "LLR", "Driving License", "Money Transfer", "PF Claim Withdrawal",
    "Bike Insurance Payment", "Birth and Death Certificate", "Police Verification",
    "Patta Chitta", "EC", "e-Shram", "PM Kisan", "National Scholarship", "MSME",
    "FSSAI", "English and Tamil Typing", "Sabarimala Booking",
]


@pytest.mark.parametrize("name", CONTACT_ONLY)
def test_contact_only_has_no_price(name):
    r = db.get_service_options(name)
    assert r["found"] is True
    assert r["fixed_price"] is False
    assert "contact or visit the shop" in r["message"]
    assert "options" not in r


def test_contact_only_price_lookup_returns_no_price():
    r = db.get_service_price("LLR", "new")
    assert "price" not in r


# ---------- multiple matches, unknown services ----------
def test_ambiguous_tax_asks_which():
    r = db.get_service_options("tax payment")
    assert r.get("multiple_matches") is True
    names = {s["service"] for s in r["services"]}
    assert names == {"Corporation Tax Payment", "Road Tax Payment"}


def test_unknown_service_not_listed():
    r = db.get_service_options("space rocket launch")
    assert r["found"] is False
    assert "not in the shop's list" in r["message"]


def test_unknown_option_does_not_invent_price():
    r = db.get_service_price("Passport", "teleportation")
    assert r["found"] is False
    assert "price" not in r


# ---------- per-page printing ----------
def test_print_quote_math():
    r = db.calculate_order_price("Print", pages=10, color_mode="bw", paper_size="A4")
    assert r["found"] is True
    assert r["total"] == 20.0


def test_bulk_discount_applies():
    r = db.calculate_order_price("Print", pages=100, color_mode="bw", paper_size="A4")
    assert r["discount_pct"] == 10.0
    assert r["total"] == 180.0


def test_copies_multiply_pages():
    r = db.calculate_order_price("Photocopy", pages=10, color_mode="bw", copies=3)
    assert r["total_pages"] == 30


# ---------- hours ----------
def test_sunday_is_closed():
    r = db.get_shop_hours("2026-10-18")  # a Sunday
    assert r["is_closed"] is True


def test_holiday_is_closed():
    r = db.get_shop_hours("2026-01-26")
    assert r["is_closed"] is True
    assert "Holiday" in r["reason"]


def test_weekday_open():
    r = db.get_shop_hours("2026-10-12")  # a Monday
    assert r["is_closed"] is False
    assert r["open_time"] == "09:30"


# ---------- data sanity ----------
def test_service_counts():
    assert len(db.get_services()) == 40


def test_database_is_read_only_in_code():
    """Every SQL statement run by db.py must be a SELECT."""
    import re
    src = open(db.__file__, encoding="utf-8").read()
    statements = re.findall(r'execute\(\s*(?:"""|")\s*(\w+)', src)
    assert statements, "no SQL statements found, test needs updating"
    assert all(word.upper() == "SELECT" for word in statements), statements