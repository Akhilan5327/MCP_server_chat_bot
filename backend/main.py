"""
FastAPI backend for the Xerox Shop Assistant.

Run with:
    uvicorn main:app --reload --port 8000

Requires ANTHROPIC_API_KEY set in the environment, e.g.:
    export ANTHROPIC_API_KEY=sk-ant-...
"""
from dotenv import load_dotenv
load_dotenv()

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import json
import os
from fastapi.responses import FileResponse
import tempfile
from fastapi import UploadFile, File, Form
from pydantic import Field
from agent import ShopAgent
FRONTEND_PATH = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")

@app.get("/")
async def serve_frontend():
    return FileResponse(FRONTEND_PATH)

# In-memory session store: {session_id: [message history]}
# Deliberately not persisted to DB — conversation memory is short-lived only.
SESSIONS: dict[str, list] = {}

agent = ShopAgent()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await agent.start()
    yield
    await agent.stop()


app = FastAPI(title="Xerox Shop Assistant", lifespan=lifespan)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Allow the React dev server to call this API. Tighten this before production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)



class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    session_id: str = "default"


class ChatResponse(BaseModel):
    reply: str


# @app.post("/chat", response_model=ChatResponse)
# async def chat(req: ChatRequest):
#     history = SESSIONS.get(req.session_id, [])
#     reply_text, updated_history = await agent.chat(req.message, history)
#     SESSIONS[req.session_id] = updated_history
#     return ChatResponse(reply=reply_text)

@app.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute")
async def chat(request: Request, req: ChatRequest):
    history = SESSIONS.get(req.session_id, [])
    try:
        reply_text, updated_history = await agent.chat(req.message, history)
        SESSIONS[req.session_id] = updated_history
        return ChatResponse(reply=reply_text)
    except Exception as e:
        logging.getLogger("main").error("Chat failed: %s", e)
        return ChatResponse(
            reply="Sorry, I'm having trouble right now. Please call or visit the shop directly for help."
        )

MAX_PDF_SIZE_MB = 20
MAX_PDF_SIZE_BYTES = MAX_PDF_SIZE_MB * 1024 * 1024

@app.post("/upload-quote")
@limiter.limit("10/minute")
async def upload_quote(
    request: Request,
    file: UploadFile = File(...),
    service_name: str = Form("Print"),
    color_mode: str = Form("bw"),
    paper_size: str = Form("A4"),
    copies: int = Form(1),
):
    if not file.filename.lower().endswith(".pdf"):
        return {"error": "Only PDF files are supported."}

    tmp_path = None
    try:
        contents = await file.read()
        if len(contents) > MAX_PDF_SIZE_BYTES:
            return {"error": f"File is too large. Please upload a PDF under {MAX_PDF_SIZE_MB} MB."}

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        count_raw = await agent.call_tool_direct("count_pdf_pages", {"file_path": tmp_path})
        count_result = json.loads(count_raw)
        if not count_result.get("found"):
            return {"error": count_result.get("error", "Could not read the PDF.")}

        page_count = count_result["page_count"]

        quote_raw = await agent.call_tool_direct(
            "calculate_order_price",
            {
                "service_name": service_name,
                "pages": page_count,
                "color_mode": color_mode,
                "paper_size": paper_size,
                "copies": copies,
            },
        )
        quote = json.loads(quote_raw)
        return {"page_count": page_count, "quote": quote}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.get("/health")
async def health():
    return {"status": "ok", "tools_loaded": agent.tool_count}

@app.get("/test-rupee")
async def test_rupee():
    return {"message": "₹100"}