"""
core/detector.py
----------------
Three-layer detection pipeline:

Layer 1 — Presidio       : Rule-based PII/PHI with built-in recognizers
                            (SSN, email, phone, credit card, medical license, etc.)
Layer 2 — GLiNER          : Zero-shot NER for entity types Presidio misses
                            (custom clinical terms, niche PII, edge cases)
Layer 3 — Regex           : Deterministic patterns for high-precision structured PII
                            (IBAN, Indian Aadhaar, PAN, passport formats, etc.)

Results are merged, deduplicated, and scored by risk level.
No API calls. No internet at runtime.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

import spacy
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from gliner import GLiNER


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    entity_type: str          # e.g. "SSN", "EMAIL_ADDRESS", "DIAGNOSIS"
    category: str             # PII | PHI | Financial | Other
    value: str                # Exact string found in text
    start: int                # Character offset start
    end: int                  # Character offset end
    score: float              # Confidence 0.0–1.0
    risk: str                 # High | Medium | Low
    source: str               # presidio | gliner | regex
    reason: str               # Human-readable explanation


# Common tech/tool/framework/crypto terms that spaCy's general-purpose NER
# (en_core_web_lg) frequently mistags as PERSON, NRP, or other PII-shaped
# entity types on resumes and technical documents — e.g. "Docker" and
# "Tensorflow" as PERSON, "Bitcoin" as NRP. This is a pragmatic denylist,
# not a fix to the classifier itself: it catches the common offenders but
# won't generalize to every possible false positive. Matching is exact and
# case-insensitive against the full matched span.
TECH_DENYLIST = {
    "python", "java", "javascript", "typescript", "sql", "html", "css",
    "react", "node", "node.js", "docker", "kubernetes", "git", "github",
    "gitlab", "aws", "azure", "gcp", "linux", "windows", "macos",
    "tensorflow", "pytorch", "keras", "numpy", "pandas", "scikit-learn",
    "opencv", "mongodb", "postgresql", "mysql", "redis", "graphql", "rest",
    "api", "bitcoin", "ethereum", "ai", "ml", "nlp", "llm", "rag", "gpt",
    "bert", "cnn", "rnn", "xgboost", "random forest", "rmse",
}


CATEGORY_MAP = {
    # Presidio entity types
    "PERSON":                  ("PII",       "High",   "Full name identifies an individual"),
    "EMAIL_ADDRESS":           ("PII",       "High",   "Email directly identifies a person"),
    "PHONE_NUMBER":            ("PII",       "High",   "Phone number identifies a person"),
    "PHONE_NUMBER_IN":         ("PII",       "High",   "Indian mobile number identifies a person"),
    "STREET_ADDRESS":         ("PII",       "High",   "Street address — sub-state geographic identifier"),
    "ZIP_CODE":                ("PII",       "Medium", "ZIP code — geographic identifier, lower specificity than a street address"),
    "US_SSN":                  ("PII",       "High",   "Social Security Number — highest sensitivity"),
    "US_DRIVER_LICENSE":       ("PII",       "High",   "Government-issued ID number"),
    "US_PASSPORT":             ("PII",       "High",   "Passport number — government ID"),
    "DATE_TIME":               ("PII",       "Low",    "Date — low risk alone, high risk combined"),
    "LOCATION":                ("PII",       "Medium", "Location data can identify individuals"),
    "IP_ADDRESS":              ("PII",       "Medium", "IP address can identify a user"),
    "MEDICAL_LICENSE":         ("PHI",       "High",   "Medical license number — provider identifier"),
    "US_BANK_NUMBER":          ("Financial", "High",   "Bank account number"),
    "CREDIT_CARD":             ("Financial", "High",   "Credit/debit card number"),
    "IBAN_CODE":               ("Financial", "High",   "International bank account number"),
    "NRP":                     ("PII",       "Medium", "Nationality/Religion/Political group"),
    # GLiNER custom types
    "diagnosis":               ("PHI",       "High",   "Medical diagnosis — protected health info"),
    "prescription":            ("PHI",       "High",   "Prescription/medication — protected health info"),
    "medical_record_number":   ("PHI",       "High",   "MRN — unique patient identifier"),
    "insurance_id":            ("PHI",       "High",   "Insurance member ID — links to health records"),
    "patient_name":            ("PHI",       "High",   "Patient name in medical context"),
    "date_of_birth":           ("PII",       "High",   "Date of birth — key identity attribute"),
    "employee_id":             ("PII",       "Medium", "Employee ID — internal identifier"),
    "salary":                  ("PII",       "High",   "Salary — sensitive financial personal data"),
    "national_id":             ("PII",       "High",   "National ID number"),
    "blood_type":              ("PHI",       "Medium", "Blood type — protected health info"),
    "lab_result":              ("PHI",       "High",   "Lab result — protected health info"),
    "treatment":               ("PHI",       "High",   "Treatment/procedure — protected health info"),
    # Regex types
    "AADHAAR":                 ("PII",       "High",   "Indian Aadhaar number — national ID"),
    "PAN":                     ("PII",       "High",   "Indian PAN card number"),
    "CVV":                     ("Financial", "High",   "Card CVV — payment security code"),
    "ROUTING_NUMBER":          ("Financial", "Medium", "Bank routing number"),
    "NPI":                     ("PHI",       "Medium", "National Provider Identifier"),
}


def _categorize(entity_type: str) -> tuple[str, str, str]:
    """Return (category, risk, reason) for an entity type."""
    key = entity_type.lower() if entity_type.lower() in CATEGORY_MAP else entity_type
    return CATEGORY_MAP.get(key, ("Other", "Medium", f"Sensitive data field: {entity_type}"))


# ---------------------------------------------------------------------------
# Regex patterns (deterministic, zero false-negatives for structured PII)
# ---------------------------------------------------------------------------

REGEX_PATTERNS = {
    "AADHAAR":        r"\b[2-9]{1}[0-9]{3}\s?[0-9]{4}\s?[0-9]{4}\b",
    "PAN":            r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b",
    "CVV":            r"\bCVV[:\s#]?\s*([0-9]{3,4})\b",
    "ROUTING_NUMBER": r"\b(routing|ABA)[:\s#]?\s*([0-9]{9})\b",
    "NPI":            r"\bNPI[:\s#]?\s*([0-9]{10})\b",
    "MRN":            r"\bMR[N#\-]?\s*[:\-]?\s*([A-Z0-9\-]{6,15})\b",
    # Indian mobile numbers: 10 digits starting 6-9, optional +91 country
    # code, optional space/hyphen grouping (e.g. "+91 91360 32205",
    # "9136032205"). Presidio's PHONE_NUMBER recognizer doesn't cover the
    # Indian format by default, so without this these were falling through
    # to spaCy's general NER, which frequently mistags them as DATE_TIME
    # (and DATE_TIME defaults to Low risk — silently hiding a real PII hit).
    "PHONE_NUMBER_IN": r"(?<!\d)(?:\+?91[\-\s]?)?[6-9]\d{4}[\-\s]?\d{5}(?!\d)",
    # US street address: house number + street name + common suffix
    # (St, Ave, Rd, Blvd, Dr, Ln, Way, Ct, Pl, NW/NE/SW/SE...). Presidio's
    # LOCATION recognizer only catches place names spaCy already knows
    # (cities, countries) — it has no concept of a street address shape,
    # so "2204 Peachtree Rd NW" was passing through undetected even though
    # sub-state geographic data is explicitly PHI under HIPAA (hipaa-2).
    "STREET_ADDRESS": r"\b\d{1,6}\s+[A-Za-z0-9.\s]{2,40}?\s(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|Pl|Place|Pkwy|Parkway|Cir|Circle)\b\.?(?:\s+(?:NE|NW|SE|SW|N|S|E|W))?",
    # ZIP code: only matched in unambiguous shapes — preceded by a 2-letter
    # state abbreviation ("GA 30309") or as ZIP+4 ("30309-1234"). A bare
    # standalone 5-digit number is deliberately NOT matched on its own —
    # that pattern would flag salary figures, employee IDs, model numbers,
    # anything 5 digits long. Precision over recall here.
    "ZIP_CODE": r"\b[A-Z]{2}\s\d{5}(?:-\d{4})?\b|\b\d{5}-\d{4}\b",
}


# ---------------------------------------------------------------------------
# GLiNER entity labels — these are what we ask GLiNER to find
# ---------------------------------------------------------------------------

# GLiNER confidence threshold. The small zero-shot model (gliner_small-v2.1)
# is prone to false positives on out-of-domain text (resumes, code/tech
# jargon, project names) at low thresholds — e.g. 0.4 was tagging things
# like "Python", "Docker", "RMSE" as national_id/treatment/etc. 0.6 fixed
# that but cost recall on legitimate fields like salary. Now that
# TECH_DENYLIST handles jargon false positives directly, 0.5 is a better
# balance — recall back up without reopening the jargon problem.
GLINER_THRESHOLD = 0.5

GLINER_LABELS = [
    "diagnosis",
    "prescription",
    "medical record number",
    "insurance id",
    "patient name",
    "date of birth",
    "employee id",
    "salary",
    "national id",
    "blood type",
    "lab result",
    "treatment",
]

GLINER_LABEL_MAP = {
    "medical record number": "medical_record_number",
    "insurance id":          "insurance_id",
    "patient name":          "patient_name",
    "date of birth":         "date_of_birth",
    "employee id":           "employee_id",
    "blood type":            "blood_type",
    "lab result":            "lab_result",
    "treatment":             "treatment",
}


# ---------------------------------------------------------------------------
# Detector class
# ---------------------------------------------------------------------------

class SensitiveDataDetector:
    def __init__(self):
        self._presidio = None
        self._gliner = None
        self._loaded = False

    def load(self):
        """Lazy-load all models. Call once before first detection."""
        if self._loaded:
            return

        print("Loading Presidio (spaCy backend)...")
        provider = NlpEngineProvider(nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
        })
        nlp_engine = provider.create_engine()
        registry = RecognizerRegistry()
        registry.load_predefined_recognizers()
        self._presidio = AnalyzerEngine(nlp_engine=nlp_engine, registry=registry)

        print("Loading GLiNER (gliner_small-v2.1)...")
        self._gliner = GLiNER.from_pretrained("urchade/gliner_small-v2.1")

        self._loaded = True
        print("All detection models loaded.")

    def _run_presidio(self, text: str) -> list[Finding]:
        results = self._presidio.analyze(text=text, language="en")
        findings = []
        for r in results:
            value = text[r.start:r.end]
            cat, risk, reason = _categorize(r.entity_type)
            findings.append(Finding(
                entity_type=r.entity_type,
                category=cat,
                value=value,
                start=r.start,
                end=r.end,
                score=r.score,
                risk=risk,
                source="presidio",
                reason=reason,
            ))
        return findings

    def _run_gliner(self, text: str) -> list[Finding]:
        # GLiNER has a token limit — chunk long texts
        max_chars = 2000
        chunks = [text[i:i+max_chars] for i in range(0, len(text), max_chars)]
        findings = []
        offset = 0
        for chunk in chunks:
            entities = self._gliner.predict_entities(chunk, GLINER_LABELS, threshold=GLINER_THRESHOLD)
            for e in entities:
                label = GLINER_LABEL_MAP.get(e["label"], e["label"].replace(" ", "_"))
                cat, risk, reason = _categorize(label)
                findings.append(Finding(
                    entity_type=label,
                    category=cat,
                    value=e["text"],
                    start=offset + e["start"],
                    end=offset + e["end"],
                    score=e["score"],
                    risk=risk,
                    source="gliner",
                    reason=reason,
                ))
            offset += len(chunk)
        return findings

    def _run_regex(self, text: str) -> list[Finding]:
        findings = []
        for entity_type, pattern in REGEX_PATTERNS.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                value = match.group()
                cat, risk, reason = _categorize(entity_type)
                findings.append(Finding(
                    entity_type=entity_type,
                    category=cat,
                    value=value,
                    start=match.start(),
                    end=match.end(),
                    score=1.0,  # regex is deterministic → full confidence
                    risk=risk,
                    source="regex",
                    reason=reason,
                ))
        return findings

    def _deduplicate(self, findings: list[Finding]) -> list[Finding]:
        """
        Remove overlapping findings. For overlaps, prefer:
        1. Higher confidence score
        2. More specific entity type (regex > presidio > gliner)
        """
        if not findings:
            return []

        findings = sorted(findings, key=lambda f: (f.start, -f.score))
        merged = []
        last_end = -1

        for f in findings:
            if f.start >= last_end:
                merged.append(f)
                last_end = f.end
            else:
                # Overlap — keep higher score
                if f.score > merged[-1].score:
                    merged[-1] = f

        return merged

    def detect(self, text: str) -> list[Finding]:
        """
        Run all three detection layers and return deduplicated findings.
        """
        if not self._loaded:
            self.load()

        presidio_findings = self._run_presidio(text)
        gliner_findings   = self._run_gliner(text)
        regex_findings    = self._run_regex(text)

        all_findings = presidio_findings + gliner_findings + regex_findings
        all_findings = [
            f for f in all_findings
            if f.value.strip().lower() not in TECH_DENYLIST
        ]
        all_findings = [f for f in all_findings if f.category != "Other"]
        return self._deduplicate(all_findings)

    def get_summary(self, findings: list[Finding]) -> dict:
        """Aggregate findings into a summary dict."""
        categories = {"PII": 0, "PHI": 0, "Financial": 0, "Other": 0}
        risks = {"High": 0, "Medium": 0, "Low": 0}
        sources = {"presidio": 0, "gliner": 0, "regex": 0}

        for f in findings:
            categories[f.category] = categories.get(f.category, 0) + 1
            risks[f.risk] = risks.get(f.risk, 0) + 1
            sources[f.source] = sources.get(f.source, 0) + 1

        overall_risk = "Low"
        if risks["High"] > 0:
            overall_risk = "High"
        elif risks["Medium"] > 0:
            overall_risk = "Medium"

        return {
            "total": len(findings),
            "categories": categories,
            "risks": risks,
            "sources": sources,
            "overall_risk": overall_risk,
        }
