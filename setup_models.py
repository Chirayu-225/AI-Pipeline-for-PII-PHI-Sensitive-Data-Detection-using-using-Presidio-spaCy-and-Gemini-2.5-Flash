"""
setup_models.py
---------------
Run this ONCE to download all model weights locally and verify your
Gemini API key is set. Detection runs fully offline after this; the
reasoning step still needs internet to call the Gemini API.

Usage:
    python setup_models.py

For fully manual download (air-gapped), see README.md.
"""

import os
from pathlib import Path

MODELS_DIR = Path("./models")
MODELS_DIR.mkdir(exist_ok=True)


def download_spacy_model():
    print("\n[1/4] Downloading spaCy model (en_core_web_lg)...")
    os.system("python -m spacy download en_core_web_lg")
    print("      ✓ spaCy model ready")


def download_gliner_model():
    print("\n[2/4] Downloading GLiNER model (gliner_small-v2.1)...")
    from gliner import GLiNER
    # Downloads and caches to ~/.cache/huggingface/
    model = GLiNER.from_pretrained("urchade/gliner_small-v2.1")
    print("      ✓ GLiNER model ready")


def download_embedding_model():
    print("\n[3/4] Downloading embedding model (all-MiniLM-L6-v2)...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    model.save(str(MODELS_DIR / "all-MiniLM-L6-v2"))
    print(f"      ✓ Embedding model saved to {MODELS_DIR / 'all-MiniLM-L6-v2'}")


def check_gemini_key():
    """
    The reasoning layer calls the Gemini API, not a local model — there's
    nothing to download here, just a check that GEMINI_API_KEY is set
    (either as a real environment variable or in a .env file).
    """
    print("\n[4/4] Checking for GEMINI_API_KEY...")
    from dotenv import load_dotenv
    load_dotenv()

    if os.environ.get("GEMINI_API_KEY"):
        print("      ✓ GEMINI_API_KEY found")
    else:
        print("      ✗ GEMINI_API_KEY not set.")
        print("        Get a free key at https://aistudio.google.com/apikey")
        print("        Then add it to a .env file: GEMINI_API_KEY=your_key_here")


if __name__ == "__main__":
    print("=" * 55)
    print("  Sensitive Data Detector — One-time Model Setup")
    print("=" * 55)
    print("This downloads all models. Internet needed only here.")
    print("After this, the app runs fully offline.\n")

    download_spacy_model()
    download_gliner_model()
    download_embedding_model()
    check_gemini_key()

    print("\n" + "=" * 55)
    print("  All models ready. Run: streamlit run app.py")
    print("=" * 55)
