import uuid
import csv
import json
import io
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from jinja2 import Environment, BaseLoader
import weasyprint


class Settings(BaseSettings):
    database_url: str = "postgresql://reviewguard:reviewguard_secret@localhost:5432/reviewguard"
    reports_dir: str = "/app/reports"

    class Config:
        env_file = ".env"


settings = Settings()
REPORTS_DIR = Path(settings.reports_dir)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    pool_pre_ping=True,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    async with SessionLocal() as session:
        yield session


app = FastAPI(title="ReviewGuard – Reporting Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<style>
  body { font-family: Arial, sans-serif; font-size: 12px; margin: 40px; }
  h1 { color: #1a1a2e; }
  table { width: 100%; border-collapse: collapse; margin-top: 20px; }
  th { background: #1a1a2e; color: white; padding: 8px; text-align: left; }
  td { padding: 6px 8px; border-bottom: 1px solid #ddd; }
  .risk-high { color: #dc2626; font-weight: bold; }
  .risk-med  { color: #d97706; }
  .risk-low  { color: #16a34a; }
  .badge { display: inline-block; padding: 2px 6px; border-radius: 4px;
           font-size: 10px; font-weight: bold; margin-right: 3px; }
  .badge-red   { background: #fee2e2; color: #dc2626; }
  .badge-amber { background: #fef3c7; color: #92400e; }
</style>
</head>
<body>
<h1>ReviewGuard – Prüfbericht</h1>
<p>Erstellt: {{ generated_at }} | Bewertungen: {{ reviews|length }}</p>
<table>
  <tr>
    <th>Datum</th><th>Plattform</th><th>Sterne</th>
    <th>Risiko-Score</th><th>Flags</th><th>Inhalt (Auszug)</th>
  </tr>
  {% for r in reviews %}
  <tr>
    <td>{{ r.review_date or r.ingested_at }}</td>
    <td>{{ r.platform }}</td>
    <td>{{ r.rating or '–' }}</td>
    <td class="{{ 'risk-high' if r.overall_risk_score >= 0.65 else ('risk-med' if r.overall_risk_score >= 0.35 else 'risk-low') }}">
      {{ "%.0f%%"|format(r.overall_risk_score * 100) if r.overall_risk_score is not none else '–' }}
    </td>
    <td>
      {% if r.is_insult %}<span class="badge badge-red">Beleidigung</span>{% endif %}
      {% if r.is_spam   %}<span class="badge badge-amber">Spam</span>{% endif %}
      {% if r.is_fake   %}<span class="badge badge-red">Fake</span>{% endif %}
      {% if r.has_false_claims %}<span class="badge badge-red">Falschaussage</span>{% endif %}
      {% if r.is_toxic  %}<span class="badge badge-red">Toxisch</span>{% endif %}
    </td>
    <td>{{ r.content[:120] }}{% if r.content|length > 120 %}…{% endif %}</td>
  </tr>
  {% endfor %}
</table>
</body>
</html>
"""


async def _fetch_reviews_with_classifications(
    db: AsyncSession,
    review_ids: list[str] | None,
    min_risk: float | None,
) -> list[dict]:
    where_clauses = []
    params: dict = {}

    if review_ids:
        where_clauses.append("r.id = ANY(:ids)")
        params["ids"] = review_ids
    if min_risk is not None:
        where_clauses.append("c.overall_risk_score >= :min_risk")
        params["min_risk"] = min_risk

    where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    result = await db.execute(
        text(f"""
            SELECT r.id, r.platform, r.content, r.rating, r.review_date, r.ingested_at,
                   c.overall_risk_score, c.is_insult, c.is_spam, c.is_fake,
                   c.has_false_claims, c.is_toxic, c.reasoning, c.flagged_phrases
            FROM reviews r
            LEFT JOIN classifications c ON c.review_id = r.id
            {where}
            ORDER BY c.overall_risk_score DESC NULLS LAST
        """),
        params,
    )
    return [dict(row._mapping) for row in result.fetchall()]


class ReportRequest(BaseModel):
    format: Literal["pdf", "csv", "json"]
    review_ids: list[str] | None = None
    min_risk_score: float | None = None


@app.post("/reports/generate")
async def generate_report(body: ReportRequest, db: AsyncSession = Depends(get_db)):
    rows = await _fetch_reviews_with_classifications(db, body.review_ids, body.min_risk_score)
    now = datetime.utcnow()
    report_id = str(uuid.uuid4())

    if body.format == "json":
        content = json.dumps(rows, default=str, ensure_ascii=False, indent=2)
        file_path = REPORTS_DIR / f"{report_id}.json"
        file_path.write_text(content, encoding="utf-8")
        media_type = "application/json"

    elif body.format == "csv":
        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        content = output.getvalue()
        file_path = REPORTS_DIR / f"{report_id}.csv"
        file_path.write_text(content, encoding="utf-8")
        media_type = "text/csv"

    else:  # pdf
        env = Environment(loader=BaseLoader())
        tmpl = env.from_string(REPORT_TEMPLATE)
        html = tmpl.render(reviews=rows, generated_at=now.strftime("%d.%m.%Y %H:%M"))
        file_path = REPORTS_DIR / f"{report_id}.pdf"
        weasyprint.HTML(string=html).write_pdf(str(file_path))
        media_type = "application/pdf"

    await db.execute(
        text("""
            INSERT INTO reports (id, created_at, report_type, review_ids, format, file_path)
            VALUES (:id, :created_at, 'custom', :review_ids, :format, :file_path)
        """),
        {
            "id": report_id,
            "created_at": now,
            "review_ids": [r["id"] for r in rows],
            "format": body.format,
            "file_path": str(file_path),
        },
    )
    await db.commit()

    return {"report_id": report_id, "format": body.format, "review_count": len(rows)}


@app.get("/reports/{report_id}/download")
async def download_report(report_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("SELECT file_path, format FROM reports WHERE id = :id"),
        {"id": report_id},
    )
    row = result.mappings().first()
    if not row or not row["file_path"]:
        return Response(status_code=404)
    return FileResponse(row["file_path"], media_type=f"application/{row['format']}")


@app.get("/reports")
async def list_reports(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("SELECT id, created_at, report_type, format FROM reports ORDER BY created_at DESC LIMIT 50")
    )
    return [dict(r._mapping) for r in result.fetchall()]


@app.get("/health")
async def health():
    return {"status": "ok", "service": "reporting"}
