import uuid
from datetime import datetime
from sqlalchemy import String, Text, SmallInteger, Boolean, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255))
    reviewer_name: Mapped[str | None] = mapped_column(String(255))
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    review_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    url: Mapped[str | None] = mapped_column(Text)
    raw_data: Mapped[dict | None] = mapped_column(JSON)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
