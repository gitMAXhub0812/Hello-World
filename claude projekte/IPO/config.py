import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

EMAIL_SENDER    = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD  = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", "")
SMTP_HOST       = os.getenv("SMTP_HOST", "mail.gmx.net")
SMTP_PORT       = int(os.getenv("SMTP_PORT", "587"))

DATA_FILE = Path(__file__).parent / "ipo_data.json"
