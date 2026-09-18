"""
MCP server for the Xerox Shop Assistant.

Exposes read-only business tools backed by SQLite (database/db.py).
The LLM agent (MCP client) calls these tools instead of ever guessing
prices, hours, or services from memory.

Requires the `mcp` SDK, which is NOT installed in this dev sandbox
(no network access here). On your own machine, set up with:

    pip install mcp

Run with:
    python server.py
"""
import sys
import os

# Allow importing database/db.py regardless of where this script is run from
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "database"))
import db  # noqa: E402

print("DB MODULE LOADED FROM:", db.__file__)
print("DB HAS get_service_price:", hasattr(db, "get_service_price"))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("xerox-shop-assistant", host="127.0.0.1", port=8001)

@mcp.tool()
def get_services() -> list:
    """List all services the shop offers, with descriptions and categories."""
    return db.get_services()


@mcp.tool()
def get_shop_hours(day: str = "today") -> dict:
    """
    Get the shop's open/close time for a given day.

    Args:
        day: 'today', 'tomorrow', a weekday name (e.g. 'Monday'), or an
             ISO date string 'YYYY-MM-DD'. Defaults to 'today'.
    """
    return db.get_shop_hours(day)


@mcp.tool()
def is_shop_open_now() -> dict:
    """Check whether the shop is open right at this exact moment."""
    return db.is_open_now()


@mcp.tool()
def get_print_price(service_name: str, color_mode: str, paper_size: str = "A4") -> dict:
    """
    Get the per-page price for a service.

    Args:
        service_name: e.g. 'Print', 'Photocopy'
        color_mode: 'bw' or 'color'
        paper_size: e.g. 'A4', 'A3'. Defaults to 'A4'.
    """
    return db.get_print_price(service_name, color_mode, paper_size)

@mcp.tool()
def get_service_price(service_name: str, service_option: str) -> dict:
    """
    Get the fixed price for a service such as Aadhar, PAN card,
    Passport, or Income Certificate.

    Args:
        service_name: e.g. 'Aadhar card', 'Pancard', 'Passport'
        service_option: e.g. 'Name Change', 'Address Change',
                        'New Application'
    """
    return db.get_service_price(service_name, service_option)

@mcp.tool()
def get_service_options(service_name: str) -> dict:
    """
    List all valid service_option values and their prices for a fixed-fee
    service (Aadhar card, Pancard, Passport, Income Certificate). Call this
    FIRST if you're unsure what options exist for a service — never guess
    option names.

    Args:
        service_name: e.g. 'Aadhar card', 'Pancard', 'Passport', 'Income Certificate'
    """
    return db.get_service_options(service_name)

@mcp.tool()
def calculate_order_price(
    service_name: str,
    pages: int,
    color_mode: str,
    paper_size: str = "A4",
    copies: int = 1,
    add_on_names: list = None,
) -> dict:
    """
    Calculate a full itemized price quote — base cost, bulk discount, add-ons, total.
    Does NOT create an order. This is a quote only; the customer must visit or
    call the shop to actually place the order.

    Args:
        service_name: e.g. 'Print', 'Photocopy'
        pages: number of pages in one copy of the document
        color_mode: 'bw' or 'color'
        paper_size: e.g. 'A4', 'A3'. Defaults to 'A4'.
        copies: number of copies requested. Defaults to 1.
        add_on_names: optional list of add-on names, e.g. ['Spiral Binding']
    """
    return db.calculate_order_price(
        service_name=service_name,
        pages=pages,
        color_mode=color_mode,
        paper_size=paper_size,
        copies=copies,
        add_on_names=add_on_names or [],
    )


@mcp.tool()
def get_faq_info(query: str) -> list:
    """
    Search shop FAQ/policy info by keyword — payment methods, turnaround time,
    accepted file formats, minimum order rules, etc.

    Args:
        query: a keyword or short phrase, e.g. 'payment', 'turnaround', 'file format'
    """
    return db.get_faq_info(query)


@mcp.tool()
def count_pdf_pages(file_path: str) -> dict:
    """
    Count pages in an uploaded PDF file, for automatic quoting.
    Reads the file only — never stores or writes anything.

    Args:
        file_path: path to a temporary uploaded PDF file
    """
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        return {"found": True, "page_count": len(reader.pages)}
    except Exception as e:
        return {"found": False, "error": str(e)}

if __name__ == "__main__":
    mcp.run(transport="streamable-http")