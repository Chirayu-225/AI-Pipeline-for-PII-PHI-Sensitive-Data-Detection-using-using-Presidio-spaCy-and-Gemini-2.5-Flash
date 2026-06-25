"""
core/redactor.py
----------------
Takes detected findings and applies redaction strategies:

  - REDACT   : Replace with [ENTITY_TYPE] placeholder
  - MASK     : Replace with *** keeping length (e.g. ***-**-1234 for SSN)
  - REPLACE  : Substitute with a fake synthetic value
  - HIGHLIGHT: Return HTML with colour-coded spans (for UI preview)

Uses Presidio Anonymizer for REDACT/MASK/REPLACE,
and custom logic for the HIGHLIGHT HTML view.
"""

from dataclasses import dataclass
from typing import Literal

from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import (
    RecognizerResult,
    OperatorConfig,
)
from presidio_analyzer.recognizer_result import RecognizerResult as AnalyzerResult

from detector import Finding


# ---------------------------------------------------------------------------
# Colour coding for highlight view
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Colour coding for highlight view — by RISK LEVEL, not category.
#   High risk (the actual sensitive PII/PHI/Financial data)  -> red
#   Medium risk (lesser-confidential data)                    -> yellow
#   Low risk / anything else                                 -> green
# ---------------------------------------------------------------------------

RISK_COLOURS = {
    "High":   {"bg": "#fee2e2", "text": "#991b1b", "border": "#fca5a5"},  # red
    "Medium": {"bg": "#fef9c3", "text": "#854d0e", "border": "#fde047"},  # yellow
    "Low":    {"bg": "#dcfce7", "text": "#166534", "border": "#86efac"},  # green
}


# ---------------------------------------------------------------------------
# Redactor
# ---------------------------------------------------------------------------

class Redactor:
    def __init__(self):
        self._engine = AnonymizerEngine()

    def redact(
        self,
        text: str,
        findings: list[Finding],
        mode: Literal["redact", "mask", "replace"] = "redact",
    ) -> str:
        """
        Apply redaction to text using Presidio Anonymizer.
        Returns the anonymized string.
        """
        if not findings:
            return text

        # Convert Finding objects → Presidio RecognizerResult objects
        analyzer_results = [
            AnalyzerResult(
                entity_type=f.entity_type,
                start=f.start,
                end=f.end,
                score=f.score,
            )
            for f in findings
        ]

        if mode == "redact":
            operators = {"DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"})}
            # Use entity-specific placeholders
            for f in findings:
                operators[f.entity_type] = OperatorConfig(
                    "replace", {"new_value": f"[{f.entity_type}]"}
                )

        elif mode == "mask":
            operators = {
                "DEFAULT": OperatorConfig("mask", {
                    "type": "mask",
                    "masking_char": "*",
                    "chars_to_mask": 999,
                    "from_end": False,
                })
            }
            # For SSN, keep last 4 digits
            operators["US_SSN"] = OperatorConfig("mask", {
                "type": "mask",
                "masking_char": "*",
                "chars_to_mask": 7,
                "from_end": False,
            })
            # For credit cards, keep last 4
            operators["CREDIT_CARD"] = OperatorConfig("mask", {
                "type": "mask",
                "masking_char": "*",
                "chars_to_mask": 12,
                "from_end": False,
            })

        elif mode == "replace":
            operators = {
                "DEFAULT":        OperatorConfig("replace", {"new_value": "[SYNTHETIC]"}),
                "PERSON":         OperatorConfig("replace", {"new_value": "Jane Smith"}),
                "EMAIL_ADDRESS":  OperatorConfig("replace", {"new_value": "user@example.com"}),
                "PHONE_NUMBER":   OperatorConfig("replace", {"new_value": "+1-555-000-0000"}),
                "US_SSN":         OperatorConfig("replace", {"new_value": "000-00-0000"}),
                "CREDIT_CARD":    OperatorConfig("replace", {"new_value": "4111-1111-1111-1111"}),
                "LOCATION":       OperatorConfig("replace", {"new_value": "123 Example St"}),
                "DATE_TIME":      OperatorConfig("replace", {"new_value": "01/01/1900"}),
            }
        else:
            raise ValueError(f"Unknown redaction mode: {mode}")

        result = self._engine.anonymize(
            text=text,
            analyzer_results=analyzer_results,
            operators=operators,
        )
        return result.text

    def highlight_html(self, text: str, findings: list[Finding]) -> str:
        """
        Return HTML string with sensitive findings wrapped in
        colour-coded <span> tags. Used for the Streamlit preview.
        """
        if not findings:
            return f"<pre style='white-space:pre-wrap;word-break:break-word;'>{_escape(text)}</pre>"

        # Sort by position descending so we can insert HTML without shifting offsets
        sorted_findings = sorted(findings, key=lambda f: f.start, reverse=True)

        chars = list(text)

        for f in sorted_findings:
            colours = RISK_COLOURS.get(f.risk, RISK_COLOURS["Low"])
            original = text[f.start:f.end]
            span = (
                f'<span style="background:{colours["bg"]};color:{colours["text"]};'
                f'border:1px solid {colours["border"]};border-radius:3px;'
                f'padding:1px 4px;font-weight:600;cursor:pointer;" '
                f'title="{f.entity_type} | {f.category} | {f.risk} risk | via {f.source}">'
                f'{_escape(original)}'
                f'</span>'
            )
            chars[f.start:f.end] = list(span)

        highlighted = "".join(chars)
        return (
            f"<pre style='white-space:pre-wrap;word-break:break-word;"
            f"font-family:monospace;font-size:13px;line-height:1.8;'>"
            f"{highlighted}</pre>"
        )

    def redact_structured(
        self,
        data: dict | list,
        findings: list[Finding],
        source_text: str,
        mode: str = "redact",
    ) -> dict | list:
        """
        For JSON/structured input: redact the source text and
        re-parse it back. Best-effort — returns redacted text
        if re-parsing fails.
        """
        redacted_text = self.redact(source_text, findings, mode)
        import json
        try:
            return json.loads(redacted_text)
        except Exception:
            return redacted_text


def _escape(text: str) -> str:
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
