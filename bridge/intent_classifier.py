"""
AI Factory — Bridge Intent Classifier
Classifies Boss input into one of 6 intent categories using Claude Haiku.
NLSpec Section 16.3
"""

from __future__ import annotations
import json
import os
from typing import Optional

CLASSIFIER_MODEL = os.environ.get("BRIDGE_CLASSIFIER_MODEL", "claude-haiku-4-5")
LITELLM_URL = os.environ.get("LITELLM_PROXY_URL", "http://localhost:4000")
CONFIDENCE_THRESHOLD = 0.80

INTENT_CLASSES = ["STATUS", "INQUIRY", "DIRECTIVE", "FEATURE", "OVERRIDE", "EMERGENCY"]

CLASSIFICATION_PROMPT = """Classify the following Boss input into one of these intent categories:
- STATUS: Request for operational information ("how is it going?", "what happened last run?")
- INQUIRY: Question about operations, content, or architecture
- DIRECTIVE: Strategic guidance that changes factory behavior ("add this source", "pause on Sundays")
- FEATURE: Request for new functionality ("add a podcast edition")
- OVERRIDE: Request to change a safety boundary or Leash constraint
- EMERGENCY: Pause, stop, kill, or rollback request

Boss input: {input}

Return ONLY valid JSON: {{"intent": "CATEGORY", "confidence": 0.0-1.0, "summary": "one sentence"}}"""


def classify(boss_input: str, llm_caller=None) -> dict:
    """
    Classify Boss input intent.
    Returns dict: {intent, confidence, summary}
    If confidence < 80%, intent is "CLARIFICATION_NEEDED".
    """
    if llm_caller is None:
        llm_caller = _call_haiku

    try:
        result = llm_caller(CLASSIFICATION_PROMPT.format(input=boss_input[:500]))
        if isinstance(result, str):
            result = json.loads(result)

        intent = result.get("intent", "INQUIRY").upper()
        confidence = float(result.get("confidence", 0.5))
        summary = result.get("summary", boss_input[:80])

        if intent not in INTENT_CLASSES:
            intent = "INQUIRY"
            confidence = 0.5

        if confidence < CONFIDENCE_THRESHOLD:
            return {
                "intent": "CLARIFICATION_NEEDED",
                "confidence": confidence,
                "summary": summary,
                "original_intent": intent,
            }

        return {"intent": intent, "confidence": confidence, "summary": summary}

    except Exception as e:
        # Fallback: treat as INQUIRY
        return {"intent": "INQUIRY", "confidence": 0.5, "summary": boss_input[:80], "error": str(e)}


def _call_haiku(prompt: str) -> dict:
    try:
        import litellm
        litellm.api_base = LITELLM_URL
        resp = litellm.completion(
            model=CLASSIFIER_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=150,
        )
        text = resp.choices[0].message.content.strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
        return json.loads(text)
    except Exception:
        return {"intent": "INQUIRY", "confidence": 0.5, "summary": prompt[:80]}
