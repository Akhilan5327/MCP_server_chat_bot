"""
Quick manual test script for the /chat endpoint — bypasses PowerShell's
UTF-8 handling bugs entirely by using Python's requests library.

Run with: python test_chat.py
"""
import requests

BASE_URL = "http://localhost:8000"


def ask(message: str, session_id: str = "test"):
    resp = requests.post(
        f"{BASE_URL}/chat",
        json={"message": message, "session_id": session_id},
    )
    resp.raise_for_status()
    print(f"\nQ: {message}")
    print(f"A: {resp.json()['reply']}")


if __name__ == "__main__":
    ask("What services do you offer?", session_id="t_services")
    ask("Are you open right now?", session_id="t_hours")
    ask("How much for 20 pages black and white?", session_id="t_print")
    ask("What about in color?", session_id="t_print")  # SAME session_id as above, to test memory
    ask("How much is Aadhar name change?", session_id="t_aadhar")
    ask("Can I get a duplicate Aadhar card?", session_id="t_aadhar2")
    ask("What payment methods do you accept?", session_id="t_faq")