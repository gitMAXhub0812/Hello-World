import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
EMAIL_SENDER    = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD  = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", "")

DATA_FILE = Path(__file__).parent / "ipo_data.json"
LOOKAHEAD_MONTHS = 3
