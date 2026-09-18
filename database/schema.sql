-- Xerox Shop Assistant — Read-Only Schema
-- No order/customer/write tables here by design (MVP is read-only).

CREATE TABLE IF NOT EXISTS services (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,              -- e.g. "Photocopy", "Print", "Spiral Binding"
    description TEXT,                       -- shown to customers when asked "what do you offer"
    category    TEXT                        -- e.g. "printing", "binding", "lamination"
);

CREATE TABLE IF NOT EXISTS pricing (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id      INTEGER NOT NULL REFERENCES services(id),
    color_mode      TEXT NOT NULL,          -- 'bw' or 'color'
    paper_size      TEXT NOT NULL DEFAULT 'A4',  -- 'A4', 'A3', 'Legal', etc.
    price_per_page  REAL NOT NULL,
    min_charge      REAL DEFAULT 0          -- minimum bill for this line item, if any
);

-- Bulk discount tiers, applied on total page count for a print job.
CREATE TABLE IF NOT EXISTS discount_tiers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    min_pages       INTEGER NOT NULL,       -- discount applies when qty >= min_pages
    discount_pct    REAL NOT NULL           -- e.g. 10 for 10%
);

-- Add-ons like binding, lamination — flat or per-unit charges.
CREATE TABLE IF NOT EXISTS add_ons (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,              -- e.g. "Spiral Binding", "Lamination A4"
    price       REAL NOT NULL,
    unit        TEXT NOT NULL DEFAULT 'flat'  -- 'flat' or 'per_page'
);

CREATE TABLE IF NOT EXISTS shop_hours (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    day_of_week INTEGER NOT NULL UNIQUE,    -- 0=Monday ... 6=Sunday
    open_time   TEXT,                       -- 'HH:MM' 24hr, NULL if closed
    close_time  TEXT,                       -- 'HH:MM' 24hr, NULL if closed
    is_closed   INTEGER NOT NULL DEFAULT 0  -- 1 = closed all day
);

CREATE TABLE IF NOT EXISTS holidays (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL UNIQUE,       -- 'YYYY-MM-DD'
    description TEXT
);

CREATE TABLE IF NOT EXISTS faq (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    question    TEXT NOT NULL,
    answer      TEXT NOT NULL,
    category    TEXT                        -- e.g. "payment", "turnaround", "file_formats"
);

CREATE TABLE IF NOT EXISTS service_pricing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id INTEGER NOT NULL REFERENCES services(id),
    service_option TEXT NOT NULL,
    price REAL NOT NULL,
    UNIQUE(service_id, service_option)
);
