"""
Generates moderation draft texts using Claude.
Three draft types:
  platform_report  – formal report to Google / Jameda support
  owner_response   – professional reply from the doctor to the reviewer
  legal_notice     – notice template for an attorney (if content is defamatory)
"""
from __future__ import annotations

from typing import Literal
import anthropic
import openai

from app.config import settings

DraftType = Literal["platform_report", "owner_response", "legal_notice"]

SYSTEM_PROMPT = """Du bist ein professioneller Rechts- und Kommunikationsassistent
für Ärzte in Deutschland. Schreibe präzise, sachliche und rechtlich belastbare Texte.
Halte Datenschutz- und DSGVO-Anforderungen ein: Nenne keine Patientendaten."""

DRAFT_PROMPTS: dict[DraftType, str] = {
    "platform_report": """
Erstelle eine formelle Meldung an den Plattform-Support ({platform}), um folgende Bewertung
wegen Verstoßes gegen die Nutzungsbedingungen zu melden.

Bewertung:
---
{content}
---

Klassifizierungsergebnis:
{classification_summary}

Der Text soll:
- Höflich und sachlich sein
- Den konkreten Verstoß benennen (Beleidigung / Spam / Falschaussage / Fake)
- Eine klare Bitte um Prüfung und Entfernung enthalten
- Unter 300 Wörter bleiben
""",
    "owner_response": """
Verfasse eine professionelle öffentliche Antwort des Arztes auf folgende Bewertung.

Bewertung:
---
{content}
---

Der Text soll:
- Keine Patientendaten enthalten (DSGVO)
- Den Arzt nicht verteidigen, sondern deeskalierend wirken
- Zur direkten Kontaktaufnahme einladen
- Kurz und professionell sein (max. 150 Wörter)
""",
    "legal_notice": """
Erstelle eine Textvorlage für eine anwaltliche Prüfung der folgenden Bewertung
auf strafrechtliche oder wettbewerbsrechtliche Relevanz (§§ 185, 186, 187 StGB; UWG).

Bewertung:
---
{content}
---

Klassifizierungsergebnis:
{classification_summary}

Hinweis: Dieser Text ist ein Entwurf für einen Rechtsanwalt, kein fertiges Rechtsdokument.
""",
}


def _build_classification_summary(classification: dict) -> str:
    flags = []
    if classification.get("is_insult"):
        flags.append(f"Beleidigung ({classification.get('insult_confidence', 0):.0%})")
    if classification.get("is_spam"):
        flags.append(f"Spam ({classification.get('spam_confidence', 0):.0%})")
    if classification.get("is_fake"):
        flags.append(f"Fake ({classification.get('fake_confidence', 0):.0%})")
    if classification.get("has_false_claims"):
        flags.append(f"Falschbehauptungen ({classification.get('false_claims_confidence', 0):.0%})")
    if classification.get("is_toxic"):
        flags.append(f"Toxisch ({classification.get('toxic_confidence', 0):.0%})")

    flagged = ", ".join(flags) if flags else "keine"
    reasoning = classification.get("reasoning", "")
    return f"Erkannte Probleme: {flagged}\nBegründung: {reasoning}"


async def generate_draft(
    draft_type: DraftType,
    content: str,
    platform: str,
    classification: dict,
) -> str:
    summary = _build_classification_summary(classification)
    prompt = DRAFT_PROMPTS[draft_type].format(
        content=content,
        platform=platform,
        classification_summary=summary,
    )

    if settings.ai_provider == "anthropic":
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    else:
        client = openai.OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content
