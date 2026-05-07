from fastapi import FastAPI, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from pydantic_settings import BaseSettings
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text


class Settings(BaseSettings):
    database_url: str = "postgresql://reviewguard:reviewguard_secret@localhost:5432/reviewguard"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notification_from: str = "noreply@reviewguard.local"

    class Config:
        env_file = ".env"


settings = Settings()

engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    pool_pre_ping=True,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    async with SessionLocal() as session:
        yield session


app = FastAPI(title="ReviewGuard – Notification Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class HighRiskPayload(BaseModel):
    review_id: str
    risk_score: float


class NotificationSettingCreate(BaseModel):
    email: str
    risk_threshold: float = 0.65


async def send_email(to: str, subject: str, body: str) -> None:
    if not settings.smtp_user:
        return  # SMTP not configured — skip silently

    message = MIMEMultipart("alternative")
    message["From"] = settings.notification_from
    message["To"] = to
    message["Subject"] = subject
    message.attach(MIMEText(body, "html"))

    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        start_tls=True,
    )


async def dispatch_high_risk_notifications(review_id: str, risk_score: float) -> None:
    async with SessionLocal() as db:
        result = await db.execute(
            text("SELECT email FROM notification_settings WHERE is_active = TRUE AND risk_threshold <= :score"),
            {"score": risk_score},
        )
        recipients = [row[0] for row in result.fetchall()]

    pct = int(risk_score * 100)
    for email in recipients:
        await send_email(
            to=email,
            subject=f"[ReviewGuard] Neue Hochrisiko-Bewertung – Score {pct}%",
            body=f"""
            <h2>ReviewGuard – Hochrisiko-Bewertung erkannt</h2>
            <p><strong>Risiko-Score:</strong> {pct}%</p>
            <p><strong>Review-ID:</strong> {review_id}</p>
            <p>Bitte im <a href="http://localhost:3000">Dashboard</a> prüfen.</p>
            """,
        )


@app.post("/notify/high-risk", status_code=202)
async def high_risk_notification(
    payload: HighRiskPayload,
    background_tasks: BackgroundTasks,
):
    background_tasks.add_task(dispatch_high_risk_notifications, payload.review_id, payload.risk_score)
    return {"queued": True}


@app.post("/settings", status_code=201)
async def create_setting(body: NotificationSettingCreate, db: AsyncSession = Depends(get_db)):
    await db.execute(
        text("""
            INSERT INTO notification_settings (email, risk_threshold)
            VALUES (:email, :threshold)
            ON CONFLICT (email) DO UPDATE SET risk_threshold = EXCLUDED.risk_threshold
        """),
        {"email": body.email, "threshold": body.risk_threshold},
    )
    await db.commit()
    return {"ok": True}


@app.get("/settings")
async def list_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("SELECT id, email, risk_threshold, is_active FROM notification_settings"))
    return [dict(r._mapping) for r in result.fetchall()]


@app.get("/health")
async def health():
    return {"status": "ok", "service": "notification"}
