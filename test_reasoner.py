"""
test_reasoner.py
----------------
Quick standalone test for the Gemini-based reasoner.
Run this after setting GEMINI_API_KEY (env var or .env file) to confirm
the API call actually works end-to-end.

Usage:
    python test_reasoner.py
"""

from detector import Finding
from reasoner import LocalReasoner

# Fake findings — no real PII, just shaped like the real thing
test_findings = [
    Finding(
        entity_type="US_SSN",
        category="PII",
        value="482-67-3901",
        start=0,
        end=11,
        score=1.0,
        risk="High",
        source="regex",
        reason="Social Security Number — highest sensitivity",
    ),
    Finding(
        entity_type="diagnosis",
        category="PHI",
        value="Type 2 Diabetes Mellitus",
        start=20,
        end=44,
        score=0.91,
        risk="High",
        source="gliner",
        reason="Medical diagnosis — protected health info",
    ),
]

test_rules = [
    {
        "framework": "HIPAA",
        "rule": "Social Security Numbers",
        "description": "SSNs are HIPAA identifiers.",
        "entity_types": ["US_SSN"],
        "risk": "High",
        "relevance": 0.92,
    },
    {
        "framework": "HIPAA",
        "rule": "Diagnosis and treatment information",
        "description": "Clinical information is core PHI.",
        "entity_types": ["diagnosis"],
        "risk": "High",
        "relevance": 0.88,
    },
]

test_snippet = "Patient: Sarah Mitchell, SSN: 482-67-3901, Diagnosis: Type 2 Diabetes Mellitus"


def main():
    print("Testing LocalReasoner (Gemini API)...\n")
    reasoner = LocalReasoner()
    reasoner.load()

    print("\n--- explain() ---")
    result = reasoner.explain(
        findings=test_findings,
        compliance_rules=test_rules,
        text_snippet=test_snippet,
    )
    print(result)

    print("\n--- explain_finding() ---")
    result2 = reasoner.explain_finding(test_findings[0])
    print(result2)


if __name__ == "__main__":
    main()
