import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
import httpx

from app.db.session import get_db
from app.classifiers.review_classifier import classify_review, ClassificationResult
from app.classifiers.draft_generator import generate_draft, DraftType
from app.config import settings

router = APIRouter()


class ClassificationRead(BaseModel):
    id: uuid.UUID
    review_id: uuid.UUID
    classified_at: datetime
    model_used: str
    overall_risk_score: float
    is_insult: bool
    insult_confidence: float | None
    is_spam: bool
    spam_confidence: float | None
    is_fake: bool
    fake_confidence: float | None
    has_false_claims: bool
    false_claims_confidence: float | None
    is_toxic: bool
    toxic_confidence: float | None
    reasoning: str | None
    flagged_phrases: list[str] | None


class DraftRequest(BaseModel):
    draft_type: DraftType


class DraftRead(BaseModel):
    id: uuid.UUID
    review_id: uuid.UUID
    draft_type: str
    content: str
    platform: str
    status: str
    created_at: datetime


async def _get_review(db: AsyncSession, review_id: uuid.UUID) -> dict:
    result = await db.execute(
        text("SELECT id, platform, content, rating FROM reviews WHERE id = :id"),
        {"id": str(review_id)},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")
    return dict(row)


async def _notify_if_high_risk(review_id: str, risk_score: float) -> None:
    if risk_score >= settings.default_risk_threshold:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{settings.notification_service_url}/notify/high-risk",
                    json={"review_id": review_id, "risk_score": risk_score},
                )
        except Exception:
            pass


@router.post("/{review_id}", response_model=ClassificationRead, status_code=200)
async def classify_review_endpoint(
    review_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    review = await _get_review(db, review_id)

    result: ClassificationResult = await classify_review(
        content=review["content"],
        platform=review["platform"],
        rating=review["rating"],
    )

    classification_id = uuid.uuid4()
    now = datetime.utcnow()

    await db.execute(
        text("""
            INSERT INTO classifications (
                id, review_id, classified_at, model_used, overall_risk_score,
                is_insult, insult_confidence, is_spam, spam_confidence,
                is_fake, fake_confidence, has_false_claims, false_claims_confidence,
                is_toxic, toxic_confidence, reasoning, flagged_phrases, raw_ai_response
            ) VALUES (
                :id, :review_id, :classified_at, :model_used, :overall_risk_score,
                :is_insult, :insult_confidence, :is_spam, :spam_confidence,
                :is_fake, :fake_confidence, :has_false_claims, :false_claims_confidence,
                :is_toxic, :toxic_confidence, :reasoning, :flagged_phrases, :raw_ai_response
            )
            ON CONFLICT (review_id) DO UPDATE SET
                classified_at = EXCLUDED.classified_at,
                model_used = EXCLUDED.model_used,
                overall_risk_score = EXCLUDED.overall_risk_score,
                is_insult = EXCLUDED.is_insult, insult_confidence = EXCLUDED.insult_confidence,
                is_spam = EXCLUDED.is_spam, spam_confidence = EXCLUDED.spam_confidence,
                is_fake = EXCLUDED.is_fake, fake_confidence = EXCLUDED.fake_confidence,
                has_false_claims = EXCLUDED.has_false_claims,
                false_claims_confidence = EXCLUDED.false_claims_confidence,
                is_toxic = EXCLUDED.is_toxic, toxic_confidence = EXCLUDED.toxic_confidence,
                reasoning = EXCLUDED.reasoning,
                flagged_phrases = EXCLUDED.flagged_phrases,
                raw_ai_response = EXCLUDED.raw_ai_response
        """),
        {
            "id": str(classification_id),
            "review_id": str(review_id),
            "classified_at": now,
            "model_used": result.model_used,
            "overall_risk_score": result.overall_risk_score,
            "is_insult": result.is_insult,
            "insult_confidence": result.insult_confidence,
            "is_spam": result.is_spam,
            "spam_confidence": result.spam_confidence,
            "is_fake": result.is_fake,
            "fake_confidence": result.fake_confidence,
            "has_false_claims": result.has_false_claims,
            "false_claims_confidence": result.false_claims_confidence,
            "is_toxic": result.is_toxic,
            "toxic_confidence": result.toxic_confidence,
            "reasoning": result.reasoning,
            "flagged_phrases": result.flagged_phrases,
            "raw_ai_response": result.raw_ai_response,
        },
    )

    await db.execute(
        text("UPDATE reviews SET is_processed = TRUE WHERE id = :id"),
        {"id": str(review_id)},
    )
    await db.commit()

    await _notify_if_high_risk(str(review_id), result.overall_risk_score)

    return ClassificationRead(
        id=classification_id,
        review_id=review_id,
        classified_at=now,
        model_used=result.model_used,
        overall_risk_score=result.overall_risk_score,
        is_insult=result.is_insult,
        insult_confidence=result.insult_confidence,
        is_spam=result.is_spam,
        spam_confidence=result.spam_confidence,
        is_fake=result.is_fake,
        fake_confidence=result.fake_confidence,
        has_false_claims=result.has_false_claims,
        false_claims_confidence=result.false_claims_confidence,
        is_toxic=result.is_toxic,
        toxic_confidence=result.toxic_confidence,
        reasoning=result.reasoning,
        flagged_phrases=result.flagged_phrases,
    )


@router.get("/{review_id}", response_model=ClassificationRead)
async def get_classification(review_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("SELECT * FROM classifications WHERE review_id = :rid"),
        {"rid": str(review_id)},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="No classification found for this review")
    return ClassificationRead(**dict(row))


@router.post("/{review_id}/drafts", response_model=DraftRead, status_code=201)
async def create_draft(
    review_id: uuid.UUID,
    body: DraftRequest,
    db: AsyncSession = Depends(get_db),
):
    review = await _get_review(db, review_id)

    cls_result = await db.execute(
        text("SELECT row_to_json(c) AS data FROM classifications c WHERE review_id = :rid"),
        {"rid": str(review_id)},
    )
    cls_row = cls_result.mappings().first()
    classification = cls_row["data"] if cls_row else {}

    draft_text = await generate_draft(
        draft_type=body.draft_type,
        content=review["content"],
        platform=review["platform"],
        classification=classification,
    )

    draft_id = uuid.uuid4()
    now = datetime.utcnow()
    await db.execute(
        text("""
            INSERT INTO moderation_drafts (id, review_id, created_at, draft_type, platform, content, status)
            VALUES (:id, :review_id, :created_at, :draft_type, :platform, :content, 'draft')
        """),
        {
            "id": str(draft_id),
            "review_id": str(review_id),
            "created_at": now,
            "draft_type": body.draft_type,
            "platform": review["platform"],
            "content": draft_text,
        },
    )
    await db.commit()

    return DraftRead(
        id=draft_id,
        review_id=review_id,
        draft_type=body.draft_type,
        content=draft_text,
        platform=review["platform"],
        status="draft",
        created_at=now,
    )
