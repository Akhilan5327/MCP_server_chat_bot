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


def create_schema(conn):
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())


def seed(conn):
    cur = conn.cursor()

    # ---- Services ----
    services = [
        ("Photocopy", "Black & white or color photocopying", "printing"),
        ("Print", "Print documents from PDF/Word/etc.", "printing"),
        ("Spiral Binding", "Spiral binding for reports/projects", "binding"),
        ("Lamination", "Lamination for certificates/ID cards", "lamination"),
        ("Aadhar card", "Aadhar card name change , address change , phone number change", "identity"),
        ("Pancard", "Pancard card name change , address change , phone number change", "identity"),
        ("Passport", "Passport card apply,name change , address change , phone number change", "identity"),
        ("Income Certificate", "Income certificate apply", "e-sevai"),
    ]
    cur.executemany(
        "INSERT INTO services (name, description, category) VALUES (?, ?, ?)",
        services,
    )

    # Map service name -> id for pricing rows
    cur.execute("SELECT id, name FROM services")
    service_ids = {name: sid for sid, name in cur.fetchall()}

    # ---- Pricing ---- (edit these to match real shop prices)
    pricing = [
        (service_ids["Print"], "bw", "A4", 2.0, 0),
        (service_ids["Print"], "color", "A4", 10.0, 0),
        (service_ids["Print"], "bw", "A3", 4.0, 0),
        (service_ids["Print"], "color", "A3", 18.0, 0),
        (service_ids["Photocopy"], "bw", "A4", 1.5, 0),
        (service_ids["Photocopy"], "color", "A4", 8.0, 0),
    ]
    cur.executemany(
        """INSERT INTO pricing (service_id, color_mode, paper_size, price_per_page, min_charge)
           VALUES (?, ?, ?, ?, ?)""",
        pricing,
    )

        # ---- Service-specific pricing ----
    service_pricing = [
        # Aadhar
        (service_ids["Aadhar card"], "Name Change", 100.0),
        (service_ids["Aadhar card"], "Address Change", 100.0),
        (service_ids["Aadhar card"], "Phone Number Change", 100.0),

        # PAN Card
        (service_ids["Pancard"], "Name Change", 150.0),
        (service_ids["Pancard"], "Address Change", 150.0),
        (service_ids["Pancard"], "Phone Number Change", 150.0),

        # Passport
        (service_ids["Passport"], "New Application", 200.0),
        (service_ids["Passport"], "Name Change", 200.0),
        (service_ids["Passport"], "Address Change", 200.0),
        (service_ids["Passport"], "Phone Number Change", 200.0),

        # Income Certificate
        (service_ids["Income Certificate"], "Application", 100.0),
    ]

    cur.executemany(
        """INSERT INTO service_pricing
           (service_id, service_option, price)
           VALUES (?, ?, ?)""",
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
    cur.executemany(
        "INSERT INTO faq (question, answer, category) VALUES (?, ?, ?)",
        faqs,
    )

    conn.commit()


def main():
    if os.path.exists(DB_PATH):
        print(f"{DB_PATH} already exists. Delete it first if you want to reseed from scratch.")
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        create_schema(conn)
        seed(conn)
        print(f"Created and seeded {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
