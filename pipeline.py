"""
pipeline.py
-----------
Orchestrates the full detection pipeline:

  1. OCR Engine      → extract text from any input format
  2. Detector        → Presidio + GLiNER + Regex detection
  3. RAG Engine      → retrieve relevant compliance rules
  4. Reasoner        → Gemini API explanation (local detection, cloud reasoning)
  5. Redactor        → anonymize/redact the text

Single entry point: Pipeline.run(source, filename)
Returns a PipelineResult dataclass with everything the UI needs.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from ocr_engine import extract_text
from detector import SensitiveDataDetector, Finding
from redactor import Redactor
from reasoner import LocalReasoner
from rag_engine import RAGEngine


@dataclass
class PipelineResult:
    # Raw extracted text (post-OCR)
    original_text: str

    # All detected findings
    findings: list[Finding]

    # Aggregated summary
    summary: dict

    # Compliance rules retrieved via RAG
    compliance_rules: list[dict]

    # Per-framework exposure scores
    compliance_exposure: dict[str, float]

    # LLM-generated explanation
    explanation: str

    # Redacted versions
    redacted_text: str
    masked_text: str

    # HTML highlighted view
    highlighted_html: str

    # Any errors/warnings
    warnings: list[str] = field(default_factory=list)


class Pipeline:
    """
    Main pipeline. Initialise once, call run() per document.
    Models are lazy-loaded on first use.
    """

    def __init__(self, load_reasoner: bool = True):
        self._detector = SensitiveDataDetector()
        self._redactor = Redactor()
        self._rag = RAGEngine()
        self._reasoner = LocalReasoner() if load_reasoner else None
        self._initialised = False

    def initialise(self):
        """Pre-load all models. Optional — models load lazily otherwise."""
        self._detector.load()
        self._rag.load()
        if self._reasoner:
            self._reasoner.load()
        self._initialised = True

    def run(
        self,
        source: Union[str, bytes, Path],
        filename: str = "",
        redaction_mode: str = "redact",
        use_reasoner: bool = True,
    ) -> PipelineResult:
        """
        Full pipeline run.

        Args:
            source:         Raw text (str), file bytes, or Path to file
            filename:       Original filename — used to detect file type
            redaction_mode: 'redact' | 'mask' | 'replace'
            use_reasoner:   Whether to run the local LLM explanation layer

        Returns:
            PipelineResult with all outputs
        """
        warnings = []

        # ── Step 1: Extract text ──────────────────────────────────────────
        try:
            text = extract_text(source, filename)
        except Exception as e:
            warnings.append(f"Text extraction warning: {e}")
            text = source if isinstance(source, str) else ""

        if not text.strip():
            return PipelineResult(
                original_text="",
                findings=[],
                summary={"total": 0, "categories": {}, "risks": {}, "sources": {}, "overall_risk": "None"},
                compliance_rules=[],
                compliance_exposure={},
                explanation="No text could be extracted from this input.",
                redacted_text="",
                masked_text="",
                highlighted_html="<p>No text extracted.</p>",
                warnings=warnings,
            )

        # ── Step 2: Detect sensitive entities ────────────────────────────
        findings = self._detector.detect(text)
        summary = self._detector.get_summary(findings)

        # ── Step 3: RAG — retrieve compliance rules ───────────────────────
        entity_types = list({f.entity_type for f in findings})
        compliance_rules = self._rag.query(entity_types, top_k=6)
        compliance_exposure = self._rag.get_compliance_exposure(entity_types)

        # ── Step 4: Reasoning layer ───────────────────────────────────────
        explanation = ""
        if use_reasoner and self._reasoner and findings:
            try:
                explanation = self._reasoner.explain(
                    findings=findings,
                    compliance_rules=compliance_rules,
                    text_snippet=text[:500],
                )
            except Exception as e:
                explanation = f"Reasoning unavailable: {e}"
                warnings.append(str(e))
        elif not findings:
            explanation = "No sensitive data detected. This document appears safe to share."

        # ── Step 5: Redaction ─────────────────────────────────────────────
        redacted_text = self._redactor.redact(text, findings, mode=redaction_mode)
        masked_text   = self._redactor.redact(text, findings, mode="mask")
        highlighted_html = self._redactor.highlight_html(text, findings)

        return PipelineResult(
            original_text=text,
            findings=findings,
            summary=summary,
            compliance_rules=compliance_rules,
            compliance_exposure=compliance_exposure,
            explanation=explanation,
            redacted_text=redacted_text,
            masked_text=masked_text,
            highlighted_html=highlighted_html,
            warnings=warnings,
        )
