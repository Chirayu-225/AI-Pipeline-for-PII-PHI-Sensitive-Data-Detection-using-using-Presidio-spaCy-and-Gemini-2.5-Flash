
# 🛡️ AI Pipeline for PII,PHI and Sensitive Data Detection

A sensitive data detection and redaction pipeline.
Detects PII, PHI, and financial data in text, PDFs, and images, then explains
the risk in plain English and redacts it.

Built as a privacy/compliance tool for documents like medical records, HR
files, and financial statements.

---

## Architecture philosophy: local detection, cloud reasoning

The part of this pipeline that actually touches raw, unredacted document text —
OCR, NER, regex matching, redaction — runs **100% locally**. Your document
never leaves the machine for detection. Only the final reasoning step, which
generates a plain-English risk summary, calls the Gemini API.

This is a deliberate tradeoff, not an oversight: a 4-bit local LLM running on
a 4GB-VRAM GPU produces noticeably shakier compliance explanations than a
frontier model. For a tool whose output references real regulatory frameworks,
explanation quality matters enough to justify a thin cloud dependency at that
one step. Detection — the part with the actual privacy risk — stays local.

If you'd rather run the reasoning step locally too (e.g. via Ollama + Phi-3
Mini), `reasoner.py` is a single swappable module — see *Going fully local*
below.

---

## Architecture

```
Input (text / PDF / image)
        │
        ▼
┌───────────────┐
│  OCR Engine   │  EasyOCR (scanned) + PyMuPDF (digital PDF)     [LOCAL]
└───────┬───────┘
        │ extracted text
        ▼
┌─────────────────────────────────────┐
│         Detection Layer             │
│  ┌──────────┐  ┌────────┐  ┌─────┐ │
│  │ Presidio │  │ GLiNER │  │Regex│ │                          [LOCAL]
│  └──────────┘  └────────┘  └─────┘ │
│   Rule-based   Zero-shot   Patterns │
└───────┬─────────────────────────────┘
        │ findings [ entity_type, value, category, risk ]
        ▼
┌───────────────┐
│  RAG Engine   │  ChromaDB + all-MiniLM-L6-v2                  [LOCAL]
│               │  Retrieves relevant compliance rules
└───────┬───────┘  (HIPAA, GDPR, PCI-DSS, CCPA, GLBA)
        │ compliance_rules, exposure_scores
        ▼
┌───────────────┐
│   Reasoner    │  Gemini 2.5 Flash (API)                       [CLOUD]
│               │  Generates plain-English risk explanation
└───────┬───────┘
        │ explanation
        ▼
┌───────────────┐
│   Redactor    │  Presidio Anonymizer                           [LOCAL]
│               │  Redact / Mask / Replace
└───────┬───────┘
        │
        ▼
   Streamlit UI
```

---

## Stack

| Layer | Tool | Notes |
|---|---|---|
| OCR | EasyOCR + PyMuPDF | CPU-friendly, GPU optional |
| PII/PHI detection | Microsoft Presidio | 20+ built-in recognizers |
| Zero-shot NER | GLiNER (`gliner_small-v2.1`) | Catches custom entity types Presidio misses |
| Structured patterns | Regex | SSN, PAN, Aadhaar, CVV, NPI, MRN… |
| Embeddings | `all-MiniLM-L6-v2` | 80MB, runs on CPU |
| Vector DB | ChromaDB | In-process, no server needed |
| Reasoning LLM | **Gemini 2.5 Flash (API)** | Free tier — exact RPM/RPD varies by account, check [your quota page](https://aistudio.google.com/usage) |
| UI | Streamlit | |

**Detection, redaction, and compliance retrieval are fully local. Only the
reasoning step calls an external API, and free-tier usage limits apply.**

---

## What actually gets sent to the API

Worth being precise about this, since the rest of the pipeline is local:

When AI explanation is enabled, `reasoner.py` sends Gemini:
- The detected entity types, categories, and risk levels (e.g. `US_SSN, PII, High risk`)
- The matched compliance rule names and frameworks
- A short snippet (~500 characters) of the original document text, for context

Disable the "AI explanation" toggle in the sidebar to skip this step entirely
— detection, redaction, and the compliance dashboard all work without it.

---

## Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_lg
```

### 2. Get a free Gemini API key

Get one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
— no credit card required for the free tier.

Copy `.env.example` to `.env` and add your key:

```bash
cp .env.example .env
# then edit .env: GEMINI_API_KEY=your_key_here
```

### 3. Download the remaining models (one-time)

```bash
python setup_models.py
```

This downloads:
- spaCy `en_core_web_lg` (Presidio's NLP backend)
- GLiNER `gliner_small-v2.1` (~500MB)
- `all-MiniLM-L6-v2` embeddings (~80MB)
- Verifies `GEMINI_API_KEY` is set

### 4. Run

```bash
streamlit run app.py
```

---

## Project Structure

```
sentinelscan/
├── app.py              # Streamlit frontend
├── pipeline.py          # Orchestrates OCR → detect → RAG → reason → redact
├── ocr_engine.py        # EasyOCR + PyMuPDF text extraction
├── detector.py           # Presidio + GLiNER + Regex detection
├── redactor.py           # Anonymization (redact / mask / replace)
├── reasoner.py            # Gemini API explanation layer
├── rag_engine.py         # ChromaDB + MiniLM compliance retrieval
├── rules.json             # HIPAA, GDPR, PCI-DSS, CCPA, GLBA rule definitions
├── setup_models.py        # One-time model download / setup script
├── test_reasoner.py       # Standalone script to test the Gemini integration
├── .env.example            # Template for your GEMINI_API_KEY
├── requirements.txt
└── chroma_store/          # Auto-created by ChromaDB on first run
```

---

## What It Detects

**PII** — Full names, email addresses, phone numbers, SSN, passport,
driver's license, national IDs, home addresses, IP addresses, dates of
birth, employee IDs, Indian Aadhaar, PAN.

**PHI** (HIPAA-relevant) — Medical record numbers (MRN), diagnoses,
prescriptions, treatments, insurance member IDs, NPI numbers, lab results,
blood type.

**Financial** — Credit/debit card numbers, CVV codes, bank account numbers,
routing numbers, IBAN codes.

## Compliance Frameworks Covered

- **HIPAA** — 18 Safe Harbor identifiers
- **GDPR** — Article 4 personal data + Article 9 special categories
- **PCI-DSS** — Cardholder data requirements
- **CCPA** — California Consumer Privacy Act
- **GLBA** — Gramm-Leach-Bliley financial data

For each detected entity, SentinelScan retrieves the matching rule via RAG
and computes a per-framework exposure score so you can see at a glance which
regulations a document touches.

---

## Hardware Requirements

| Component | Minimum | Recommended |
|---|---|---|
| RAM | 8GB | 16GB |
| Storage | ~1GB (local models) | 2GB |
| GPU | Not required | Speeds up GLiNER inference |
| OS | Windows / macOS / Linux | |
| Internet | Required for the reasoning step only | |

---

## Going fully local

To swap the Gemini reasoner back out for a local LLM (e.g. Ollama + Phi-3
Mini), `reasoner.py` exposes the same `LocalReasoner.explain()` /
`.explain_finding()` interface that `pipeline.py` calls — no changes needed
outside that one file. Swap the implementation, keep the method signatures,
done.

---

## Roadmap / Known Limitations

- Single-document scanning only — no batch processing yet
- Redaction is text-only; doesn't re-render redacted PDFs/images with boxes
- The reasoning step depends on Gemini's free-tier rate limits, which vary
  by model and account and have tightened over time — check your usage at
  [aistudio.google.com/usage](https://aistudio.google.com/usage) if you hit
  429 errors; heavy usage may need a billed key
- AI-generated risk explanations are informational, not legal or medical
  advice — always have a human review before acting on them

---

## License

MIT
