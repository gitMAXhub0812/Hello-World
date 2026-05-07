"""
AI-based review classifier.
Sends the review text to Claude (or GPT-4o) and returns a structured
ClassificationResult that maps to the `classifications` DB table.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import anthropic
import openai

from app.config import settings

SYSTEM_PROMPT = """Du bist ein juristisch geschulter Moderationsassistent für Arztbewertungsplattformen.

Deine Aufgabe ist es, Patientenbewertungen auf problematische Inhalte zu analysieren.
Du bewertest NICHT die inhaltliche Meinung, sondern nur, ob die Bewertung
plattformrechtswidrige oder potenziell rechtswidrige Elemente enthält.

Antworte AUSSCHLIESSLICH mit einem validen JSON-Objekt (kein Markdown, kein Text davor/danach).
"""

CLASSIFICATION_PROMPT = """Analysiere folgende Arztbewertung:

PLATTFORM: {platform}
BEWERTUNG: {content}
STERNEBEWERTUNG: {rating}

Gib ein JSON-Objekt mit exakt dieser Struktur zurück:

{{
  "overall_risk_score": <float 0.0–1.0>,
  "is_insult": <bool>,
  "insult_confidence": <float 0.0–1.0>,
  "is_spam": <bool>,
  "spam_confidence": <float 0.0–1.0>,
  "is_fake": <bool>,
  "fake_confidence": <float 0.0–1.0>,
  "has_false_claims": <bool>,
  "false_claims_confidence": <float 0.0–1.0>,
  "is_toxic": <bool>,
  "toxic_confidence": <float 0.0–1.0>,
  "reasoning": "<Begründung auf Deutsch, max 300 Zeichen>",
  "flagged_phrases": ["<auffällige Textpassage 1>", ...]
}}

Definitionen:
- is_insult: persönliche Beleidigung, Beschimpfung des Arztes/Teams
- is_spam: offensichtlich irrelevant, copy-paste, Werbung, Off-Topic
- is_fake: erkennbar erfundene Identität, Bot-Muster, identische Formulierungen wie bekannte Fake-Reviews
- has_false_claims: faktisch überprüfbare Falschaussagen (z.B. "hat nie studiert")
- is_toxic: Hasssprache, Diskriminierung, explizite Drohungen
- overall_risk_score: gewichtetes Gesamtrisiko; 0.0 = kein Risiko, 1.0 = eindeutig meldungswürdig
"""


@dataclass
class ClassificationResult:
    overall_risk_score: float
    is_insult: bool
    insult_confidence: float
    is_spam: bool
    spam_confidence: float
    is_fake: bool
    fake_confidence: float
    has_false_claims: bool
    false_claims_confidence: float
    is_toxic: bool
    toxic_confidence: float
    reasoning: str
    flagged_phrases: list[str]
    model_used: str
    raw_ai_response: dict


def _parse_response(text: str, model_used: str) -> ClassificationResult:
    # strip possible markdown code fences
    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    data = json.loads(cleaned)

    return ClassificationResult(
        overall_risk_score=float(data.get("overall_risk_score", 0.0)),
        is_insult=bool(data.get("is_insult", False)),
        insult_confidence=float(data.get("insult_confidence", 0.0)),
        is_spam=bool(data.get("is_spam", False)),
        spam_confidence=float(data.get("spam_confidence", 0.0)),
        is_fake=bool(data.get("is_fake", False)),
        fake_confidence=float(data.get("fake_confidence", 0.0)),
        has_false_claims=bool(data.get("has_false_claims", False)),
        false_claims_confidence=float(data.get("false_claims_confidence", 0.0)),
        is_toxic=bool(data.get("is_toxic", False)),
        toxic_confidence=float(data.get("toxic_confidence", 0.0)),
        reasoning=str(data.get("reasoning", "")),
        flagged_phrases=list(data.get("flagged_phrases", [])),
        model_used=model_used,
        raw_ai_response=data,
    )


async def classify_review(
    content: str,
    platform: str = "unknown",
    rating: int | None = None,
) -> ClassificationResult:
    prompt = CLASSIFICATION_PROMPT.format(
        platform=platform,
        content=content,
        rating=rating if rating is not None else "k.A.",
    )

    if settings.ai_provider == "anthropic":
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        model = "claude-sonnet-4-6"
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = message.content[0].text
        return _parse_response(raw_text, model)

    else:  # openai
        client = openai.OpenAI(api_key=settings.openai_api_key)
        model = "gpt-4o"
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        raw_text = response.choices[0].message.content
        return _parse_response(raw_text, model)
