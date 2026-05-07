from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import classify


app = FastAPI(
    title="ReviewGuard – Moderation Service",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(classify.router, prefix="/classify", tags=["classification"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "moderation"}
