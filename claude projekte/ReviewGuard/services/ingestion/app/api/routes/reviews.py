import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import httpx

from app.db.session import get_db
from app.models.review import Review
from app.config import settings

router = APIRouter()

Platform = Literal["google", "jameda", "manual", "other"]


class ReviewCreate(BaseModel):
    platform: Platform
    external_id: str | None = None
    reviewer_name: str | None = None
    rating: int | None = Field(None, ge=1, le=5)
    content: str = Field(..., min_length=1)
    review_date: datetime | None = None
    url: str | None = None
    raw_data: dict | None = None


class ReviewRead(BaseModel):
    id: uuid.UUID
    platform: str
    external_id: str | None
    reviewer_name: str | None
    rating: int | None
    content: str
    review_date: datetime | None
    ingested_at: datetime
    url: str | None
    is_processed: bool

    model_config = {"from_attributes": True}


class ReviewListResponse(BaseModel):
    total: int
    items: list[ReviewRead]


async def trigger_classification(review_id: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            await client.post(f"{settings.moderation_service_url}/classify/{review_id}")
    except Exception:
        pass  # classification is best-effort; don't fail ingestion


@router.post("/", response_model=ReviewRead, status_code=201)
async def create_review(
    body: ReviewCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    review = Review(**body.model_dump())
    db.add(review)
    await db.commit()
    await db.refresh(review)
    background_tasks.add_task(trigger_classification, str(review.id))
    return review


@router.post("/batch", response_model=list[ReviewRead], status_code=201)
async def create_reviews_batch(
    body: list[ReviewCreate],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    reviews = [Review(**r.model_dump()) for r in body]
    db.add_all(reviews)
    await db.commit()
    for r in reviews:
        await db.refresh(r)
        background_tasks.add_task(trigger_classification, str(r.id))
    return reviews


@router.get("/", response_model=ReviewListResponse)
async def list_reviews(
    platform: str | None = None,
    is_processed: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    query = select(Review)
    count_query = select(func.count()).select_from(Review)

    if platform:
        query = query.where(Review.platform == platform)
        count_query = count_query.where(Review.platform == platform)
    if is_processed is not None:
        query = query.where(Review.is_processed == is_processed)
        count_query = count_query.where(Review.is_processed == is_processed)

    query = query.order_by(Review.ingested_at.desc()).limit(limit).offset(offset)

    total = (await db.execute(count_query)).scalar_one()
    items = (await db.execute(query)).scalars().all()
    return ReviewListResponse(total=total, items=list(items))


@router.get("/{review_id}", response_model=ReviewRead)
async def get_review(review_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    review = await db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@router.delete("/{review_id}", status_code=204)
async def delete_review(review_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    review = await db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    await db.delete(review)
    await db.commit()
