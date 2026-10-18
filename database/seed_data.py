"""
Creates shop.db (SQLite) from schema.sql and populates it with sample data.
Run this once to set up the database: python seed_data.py

Edit the SAMPLE_* lists below to match your father's actual shop —
this is the "source of truth" until an admin tool is built later.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "shop.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

# ---- EDIT THESE: shop details the assistant will share when customers ask ----
SHOP_NAME = "Anbhu Enterprises"
SHOP_ADDRESS = "No 1, Near Opposite to Jio Digital, Milagu Pillai Street, Pallavaram, Chennai-600043, Tamil Nadu"
SHOP_LANDMARK = "Near Jockey Showroom"      # optional, for example "Opposite the bus stand"
SHOP_PHONE = "9176369676"
SHOP_WHATSAPP = "9176369676"      # optional, leave empty if not used
SHOP_MAPS_LINK = "https://maps.app.goo.gl/S1qL7xhEshoXHFFZ7"     # optional Google Maps link


def create_schema(conn):
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())


def seed(conn):
    cur = conn.cursor()

    # ---- Services ----
    # (name, description, category)
    # Printing prices below are SAMPLE values - replace with real ones.
    services = [
        # Per-page services (priced in the `pricing` table)
        ("Photocopy", "Black & white or color photocopying", "printing"),
        ("Print", "Print documents from PDF/Word/etc.", "printing"),
        ("Spiral Binding", "Spiral binding for reports/projects", "binding"),
        ("Lamination", "Lamination for certificates/ID cards", "lamination"),

        # Fixed-price services (rows in `service_pricing`)
        ("Aadhar Card", "Aadhar card correction (name, address, mobile number, etc.)", "identity"),
        ("PAN Card", "PAN card new application and correction", "identity"),
        ("Smart Card", "Smart card new application and correction", "identity"),
        ("Passport", "Passport new application and correction", "identity"),
        ("Voter ID", "Voter ID new application and correction", "identity"),
        ("Online Certificate", "Income, community and residential certificates", "e-sevai"),
        ("Online College Application", "Online college application", "education"),
        ("Employment Registration", "Employment exchange registration", "e-sevai"),

        # Contact-only services (NO price rows -> bot says contact/visit the shop)
        ("LLR", "Learner's licence (LLR)", "transport"),
        ("Driving License", "Driving licence new and renewal", "transport"),
        ("Money Transfer", "Money transfer", "payments"),
        ("Aadhar Card Cash Withdrawal", "Cash withdrawal using Aadhar card", "payments"),
        ("PF Claim Withdrawal", "PF claim and withdrawal", "payments"),
        ("Bike Insurance Payment", "Bike insurance payment", "payments"),
        ("Challan Payment", "Police verification and traffic challan payment", "payments"),
        ("Corporation Tax Payment", "Corporation tax payment", "payments"),
        ("Road Tax Payment", "Road tax payment", "payments"),
        ("Birth and Death Certificate", "Birth and death certificate", "e-sevai"),
        ("Police Verification", "Police verification", "e-sevai"),
        ("Pensioners Life Certificate", "Pensioners life certificate", "e-sevai"),
        ("Patta Chitta", "Patta and chitta", "land"),
        ("EC", "Encumbrance Certificate (EC)", "land"),
        ("Patta Transfer", "Patta transfer", "land"),
        ("National Health Card", "National health card", "government scheme"),
        ("CM Health Card", "Chief Minister health insurance card", "government scheme"),
        ("e-Shram", "e-Shram card registration", "government scheme"),
        ("PM Kisan", "PM Kisan registration", "government scheme"),
        ("National Scholarship", "National scholarship application", "education"),
        ("Government Job Applications", "All government job applications including TNPSC, RRB, SSC", "jobs and exams"),
        ("JEE and NEET Applications", "JEE and NEET exam applications", "jobs and exams"),
        ("MSME", "MSME registration", "business"),
        ("FSSAI", "FSSAI registration", "business"),
        ("English and Tamil Typing", "English and Tamil typing", "typing"),
        ("Train, Bus and Flight Ticket Booking", "Train, bus and flight ticket booking", "booking"),
        ("Tirupati Darshan Booking", "Tirupati (Tirupathi) darshan booking", "booking"),
        ("Sabarimala Booking", "Sabarimala (Sabarimalai) booking", "booking"),
    ]
    cur.executemany(
        "INSERT INTO services (name, description, category) VALUES (?, ?, ?)",
        services,
    )

    cur.execute("SELECT id, name FROM services")
    service_ids = {name: sid for sid, name in cur.fetchall()}

    # ---- Per-page pricing ---- (SAMPLE values - edit to real prices)
    pricing = [
        (service_ids["Print"], "bw", "A4", 5.0, 0),
        (service_ids["Print"], "color", "A4", 10.0, 0),
        (service_ids["Print"], "bw", "A3", 20.0, 0),
        (service_ids["Print"], "color", "A3", 40.0, 0),
        (service_ids["Photocopy"], "bw", "A4", 1.5, 0),
        (service_ids["Photocopy"], "color", "A4", 8.0, 0),
    ]
    cur.executemany(
        """INSERT INTO pricing (service_id, color_mode, paper_size, price_per_page, min_charge)
           VALUES (?, ?, ?, ?, ?)""",
        pricing,
    )

    # ---- Fixed prices ----
    service_pricing = [
        (service_ids["Aadhar Card"], "Correction", 250.0),
        (service_ids["PAN Card"], "New Application", 300.0),
        (service_ids["PAN Card"], "Correction", 300.0),
        (service_ids["Smart Card"], "New Application", 200.0),
        (service_ids["Smart Card"], "Correction", 200.0),
        (service_ids["Passport"], "New Application", 500.0),
        (service_ids["Passport"], "Correction", 500.0),
        (service_ids["Voter ID"], "New Application", 250.0),
        (service_ids["Voter ID"], "Correction", 250.0),
        (service_ids["Online Certificate"], "Income Certificate", 300.0),
        (service_ids["Online Certificate"], "Community Certificate", 300.0),
        (service_ids["Online Certificate"], "Residential Certificate", 300.0),
        (service_ids["Online College Application"], "Application", 300.0),
        (service_ids["Employment Registration"], "Registration", 100.0),
    ]
    cur.executemany(
        "INSERT INTO service_pricing (service_id, service_option, price) VALUES (?, ?, ?)",
        service_pricing,
    )

    # ---- Discount tiers ----
    discount_tiers = [
        (50, 5.0),    # 50+ pages -> 5% off
        (100, 10.0),  # 100+ pages -> 10% off
    ]
    cur.executemany(
        "INSERT INTO discount_tiers (min_pages, discount_pct) VALUES (?, ?)",
        discount_tiers,
    )

    # ---- Add-ons ----
    add_ons = [
        ("Spiral Binding", 25.0, "flat"),
        ("Lamination A4", 15.0, "per_page"),
    ]
    cur.executemany(
        "INSERT INTO add_ons (name, price, unit) VALUES (?, ?, ?)",
        add_ons,
    )

    # ---- Shop hours ---- (0=Monday ... 6=Sunday)
    shop_hours = [
        (0, "09:30", "20:00", 0),
        (1, "09:30", "20:00", 0),
        (2, "09:30", "20:00", 0),
        (3, "09:30", "20:00", 0),
        (4, "09:30", "20:00", 0),
        (5, "09:30", "18:00", 0),
        (6, None, None, 1),  # Sunday closed
    ]
    cur.executemany(
        """INSERT INTO shop_hours (day_of_week, open_time, close_time, is_closed)
           VALUES (?, ?, ?, ?)""",
        shop_hours,
    )

    # ---- Holidays ----
    holidays = [
        ("2026-01-26", "Republic Day"),
        ("2026-08-15", "Independence Day"),
    ]
    cur.executemany(
        "INSERT INTO holidays (date, description) VALUES (?, ?)",
        holidays,
    )

    # ---- FAQ ----
    faqs = [
        ("What file formats do you accept?", "We accept PDF, DOCX, and JPG/PNG files.", "file_formats"),
        ("What is the turnaround time?", "Most orders under 50 pages are ready the same day.", "turnaround"),
        ("What payment methods do you accept?", "Cash, UPI, and card payments are all accepted.", "payment"),
        ("Is there a minimum order?", "No minimum order — even single-page prints are welcome.", "general"),
    ]
    # Location and contact answers, built from the SHOP_* values at the top of this file
    location_answer = f"{SHOP_NAME}, {SHOP_ADDRESS}."
    if SHOP_LANDMARK:
        location_answer += f" Landmark: {SHOP_LANDMARK}."
    if SHOP_MAPS_LINK:
        location_answer += f" Map: {SHOP_MAPS_LINK}"
    contact_answer = f"You can call the shop on {SHOP_PHONE}."
    if SHOP_WHATSAPP:
        contact_answer += f" WhatsApp: {SHOP_WHATSAPP}."
    faqs += [
        ("Where is the shop located? What is the shop address?", location_answer, "location"),
        ("What is the shop phone number? How can I contact the shop?", contact_answer, "contact"),
    ]
    cur.executemany(
        "INSERT INTO faq (question, answer, category) VALUES (?, ?, ?)",
        faqs,
    )

    conn.commit()


def main():
    if os.path.exists(DB_PATH):
        print(f"{DB_PATH} already exists. Delete it first if you want to reseed from scratch.")
        return
    if "REPLACE" in SHOP_ADDRESS + SHOP_PHONE:
        print("WARNING: SHOP_ADDRESS or SHOP_PHONE at the top of seed_data.py is still a placeholder.")
    conn = sqlite3.connect(DB_PATH)
    try:
        create_schema(conn)
        seed(conn)
        print(f"Created and seeded {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()