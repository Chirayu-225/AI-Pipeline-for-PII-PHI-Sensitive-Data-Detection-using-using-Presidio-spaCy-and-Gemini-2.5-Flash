"""
reasoner.py
-----------
Cloud reasoning layer using Google's Gemini API (free tier).

Sends the detected findings and matched compliance rules — plus a short
text snippet for context — to Gemini 2.5 Flash for a plain-English risk
explanation. Detection itself (Presidio/GLiNER/Regex) still runs 100%
locally; only this reasoning step makes a network call.

Requires a GEMINI_API_KEY in a .env file at the project root.
Get a free key at https://aistudio.google.com/apikey — no credit card
needed for the free tier (10 requests/min, 1,500/day as of mid-2026).
"""

import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError

from detector import Finding

load_dotenv()

MODEL_NAME = "gemini-2.5-flash"

# Retry transient errors (503 = model overloaded, 429 = rate limited)
# with exponential backoff before giving up.
RETRYABLE_CODES = {503, 429}
MAX_RETRIES = 3
BASE_DELAY_SECONDS = 2


class LocalReasoner:
    """
    Named LocalReasoner for backwards compatibility with pipeline.py —
    the reasoning step itself now runs via the Gemini API, not locally.
    """

    def __init__(self):
        self._client = None
        self._loaded = False
        self._api_key_present = False

    def load(self):
        """Initialise the Gemini client. Call once before first use."""
        if self._loaded:
            return

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print(
                "Warning: GEMINI_API_KEY not found. Add it to a .env file "
                "in the project root. Get a free key at "
                "https://aistudio.google.com/apikey"
            )
            self._api_key_present = False
        else:
            self._client = genai.Client(api_key=api_key)
            self._api_key_present = True
            print(f"Reasoner ready — using Gemini API ({MODEL_NAME})")

        self._loaded = True

    def _generate(self, prompt: str, max_tokens: int = 300) -> str:
        """Send prompt to Gemini and return response text. Retries on
        transient overload/rate-limit errors with exponential backoff."""
        if not self._api_key_present:
            return (
                "⚠ No Gemini API key configured. Add GEMINI_API_KEY to a "
                ".env file to enable AI explanations."
            )

        last_error = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self._client.models.generate_content(
                    model=MODEL_NAME,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        max_output_tokens=max_tokens,
                        temperature=0.1,
                        top_p=0.9,
                        thinking_config=types.ThinkingConfig(
                            thinking_budget=0,  # off — not needed for this task
                        ),
                    ),
                )

                # Diagnostic: show why generation stopped (helps catch
                # truncation from thinking tokens eating the budget).
                if response.candidates:
                    finish_reason = response.candidates[0].finish_reason
                    print(f"[debug] finish_reason: {finish_reason}")

                if not response.text:
                    # Most commonly: safety filters blocked the response,
                    # OR max_output_tokens was hit before the model finished
                    # "thinking" and never reached its final answer.
                    reason = getattr(response, "prompt_feedback", None)
                    finish_reason = (
                        response.candidates[0].finish_reason
                        if response.candidates else None
                    )
                    return (
                        "⚠ Gemini returned an empty response. "
                        f"finish_reason={finish_reason}, prompt_feedback={reason}"
                    )

                return response.text.strip()

            except APIError as e:
                last_error = e
                code = getattr(e, "code", None)
                if code in RETRYABLE_CODES and attempt < MAX_RETRIES:
                    delay = BASE_DELAY_SECONDS * (2 ** attempt)
                    print(
                        f"Gemini returned {code}, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{MAX_RETRIES})..."
                    )
                    time.sleep(delay)
                    continue
                return f"⚠ Gemini API error: {e}"

            except Exception as e:
                return f"⚠ Reasoner error: {e}"

        return f"⚠ Gemini API error after {MAX_RETRIES} retries: {last_error}"

    def explain(
        self,
        findings: list[Finding],
        compliance_rules: list[dict],
        text_snippet: str,
        max_new_tokens: int = 500,
    ) -> str:
        """Generate a plain-English risk explanation grounded in findings."""
        if not self._loaded:
            self.load()

        if not findings:
            return "No sensitive data was detected in this document."

        high_risk = [f for f in findings if f.risk == "High"]
        finding_lines = "\n".join(
            f"  - {f.entity_type} ({f.category}, {f.risk} risk): '{f.value[:40]}'"
            for f in findings[:12]
        )
        frameworks = list({r["framework"] for r in compliance_rules})
        rule_lines = "\n".join(
            f"  - [{r['framework']}] {r['rule']}"
            for r in compliance_rules[:5]
        )

        prompt = f"""You are a privacy compliance assistant. Be concise, specific, and factual. This is not legal advice — frame remediation as a suggestion, not a directive.

DOCUMENT SNIPPET (for context only):
{text_snippet[:500]}

DETECTED SENSITIVE DATA ({len(findings)} items, {len(high_risk)} high-risk):
{finding_lines}

APPLICABLE COMPLIANCE RULES:
{rule_lines}

RELEVANT FRAMEWORKS: {", ".join(frameworks)}

In exactly 3 sentences:
1. Summarise the overall privacy risk of this document.
2. Highlight the single most critical finding and why it matters.
3. Suggest one concrete remediation action.

Response:"""

        return self._generate(prompt, max_tokens=max_new_tokens)

    def explain_finding(self, finding: Finding, max_new_tokens: int = 250) -> str:
        """Generate a focused explanation for a single finding."""
        if not self._loaded:
            self.load()

        prompt = f"""In 2 sentences, explain why '{finding.entity_type}' ({finding.category}, {finding.risk} risk) is sensitive and which regulation typically governs it.

Response:"""
        return self._generate(prompt, max_tokens=max_new_tokens)
