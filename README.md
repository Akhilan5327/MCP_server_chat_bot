# AI-Powered Xerox Shop Assistant — Phase 1 (Read-Only MVP)

A read-only Q&A + pricing-quote assistant for a printing shop. No orders are
created and no data is written by the AI agent — every tool only reads from
SQLite and does arithmetic.

## Structure

```
xerox_shop_assistant/
├── database/
│   ├── schema.sql       # table definitions (services, pricing, hours, faq, etc.)
│   ├── seed_data.py     # creates shop.db and fills it with sample data
│   ├── db.py            # read-only query functions (plain sqlite3, no ORM)
│   └── shop.db          # created after running seed_data.py (gitignore this if it has real data)
├── mcp_server/
│   └── server.py        # MCP server exposing tools to the LLM agent
├── requirements.txt
└── README.md
```

## Setup (on your own machine — this sandbox has no internet access)

```bash
cd xerox_shop_assistant
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create and seed the database (only needs to run once)
cd database
python3 seed_data.py
cd ..

# Run the MCP server
cd mcp_server
python3 server.py
```

## Editing shop data

There's no admin write-tool yet (by design — this MVP is read-only). To
update prices, hours, or FAQs:
1. Delete `database/shop.db`
2. Edit the sample data in `database/seed_data.py`
3. Re-run `python3 seed_data.py`

For anything past the MVP stage, open `shop.db` directly with a free tool
like **DB Browser for SQLite** (https://sqlitebrowser.org) to edit rows
without touching seed_data.py at all.

## Tools exposed by the MCP server

| Tool | Purpose |
|---|---|
| `get_services()` | List all services offered |
| `get_shop_hours(day)` | Open/close time for a given day ('today', 'tomorrow', weekday name, or ISO date) |
| `is_shop_open_now()` | Is the shop open right this moment |
| `get_print_price(service_name, color_mode, paper_size)` | Per-page price lookup |
| `calculate_order_price(service_name, pages, color_mode, paper_size, copies, add_on_names)` | Full itemized quote with bulk discount + add-ons |
| `get_faq_info(query)` | Keyword search over shop policy/FAQ info |
| `count_pdf_pages(file_path)` | Count pages in an uploaded PDF, for auto-quoting |

## Verified working (tested in dev sandbox with plain sqlite3)

- Seeding the DB and querying services, hours, pricing, FAQ — all confirmed working.
- Example quote calculation (60 B/W pages + spiral binding) correctly applies
  the 5% bulk discount tier and adds the binding cost.

## What's intentionally NOT here yet

- `create_order()`, `get_order_status()`, `upload_document()` (persistent) — these
  need write access, out of scope for this read-only MVP.
- FastAPI HTTP layer connecting a chat UI to this MCP server — next step.
- React chat widget — next step.
- Admin dashboard — deferred; edit `shop.db` directly for now (see above).

## Next steps

1. Wire this MCP server up as a tool source for an LLM agent (e.g. via the
   Claude API with MCP client support, or the `mcp` Python client library).
2. Build a minimal FastAPI endpoint that takes a customer chat message,
   calls the LLM (with these tools available), and returns the reply.
3. Build the React chat widget to talk to that FastAPI endpoint.
4. For the "I want to print this PDF" flow: accept the file upload in
   FastAPI, save it to a temp path, call `count_pdf_pages()`, then
   `calculate_order_price()` — and discard the temp file afterward if you
   want to stay fully write-free.
