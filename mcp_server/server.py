"""
MCP server for the Xerox Shop Assistant.

Exposes read-only business tools backed by SQLite (database/db.py).
The LLM agent (MCP client) calls these tools instead of ever guessing
prices, hours, or services from memory.

Run with:
    python server.py
"""
import sys
import os

# Allow importing database/db.py regardless of where this script is run from
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "database"))
import db  # noqa: E402

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("xerox-shop-assistant", host="127.0.0.1", port=8001)

# NOTE: these docstrings are sent to the LLM on every call, so keep them short.
# Keep the allowed values (like 'bw' or 'color'); the model needs them.


@mcp.tool()
def get_services() -> list:
    """List all shop services with descriptions and categories."""
    return db.get_services()


@mcp.tool()
def get_shop_hours(day: str = "today") -> dict:
    """Shop open/close time. day: 'today', 'tomorrow', a weekday name, or YYYY-MM-DD."""
    return db.get_shop_hours(day)


@mcp.tool()
def is_shop_open_now() -> dict:
    """Whether the shop is open right now."""
    return db.is_open_now()


@mcp.tool()
def get_print_price(service_name: str, color_mode: str, paper_size: str = "A4") -> dict:
    """Per-page price. service_name: 'Print' or 'Photocopy'. color_mode: 'bw' or 'color'. paper_size: 'A4' (default) or 'A3'."""
    return db.get_print_price(service_name, color_mode, paper_size)


@mcp.tool()
def get_service_price(service_name: str, service_option: str) -> dict:
    """Fixed price of one service option, e.g. service_name 'Pancard', service_option 'New Application'."""
    return db.get_service_price(service_name, service_option)


@mcp.tool()
def get_service_options(service_name: str) -> dict:
    """List the valid options and prices for a service such as Aadhar card, Pancard or Passport. Call this first and never guess option names. It also says when a service has no fixed price."""
    return db.get_service_options(service_name)


@mcp.tool()
def calculate_order_price(
    service_name: str,
    pages: int,
    color_mode: str,
    paper_size: str = "A4",
    copies: int = 1,
    add_on_names: list[str] | None = None,
) -> dict:
    """Print quote with base cost, bulk discount, add-ons and total. Creates no order. service_name: 'Print' or 'Photocopy'. pages: pages in one copy. color_mode: 'bw' or 'color'. paper_size: 'A4' (default) or 'A3'. copies: default 1. add_on_names: optional list such as ['Spiral Binding']."""
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
    """Search shop FAQ by keyword: location, contact, payment, turnaround, file format, minimum order and so on."""
    return db.get_faq_info(query)


@mcp.tool()
def count_pdf_pages(file_path: str) -> dict:
    """Count pages in an uploaded PDF (read-only)."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        return {"found": True, "page_count": len(reader.pages)}
    except Exception as e:
        return {"found": False, "error": str(e)}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")