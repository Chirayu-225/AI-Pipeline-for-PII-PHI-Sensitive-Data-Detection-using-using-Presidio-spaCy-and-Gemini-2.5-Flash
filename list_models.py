"""
list_models.py
---------------
One-off diagnostic: lists every Gemini model your API key can actually call
with generateContent. Run this if reasoner.py gives a 404 NOT_FOUND error —
it tells you exactly which model name to put in reasoner.py.

Usage:
    python list_models.py
"""

import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("GEMINI_API_KEY not found in environment or .env file.")
    raise SystemExit(1)

client = genai.Client(api_key=api_key)

print("Models available to your API key that support generateContent:\n")
for model in client.models.list():
    actions = getattr(model, "supported_actions", None) or []
    if "generateContent" in actions:
        print(f"  {model.name}")
