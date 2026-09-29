# just pulls all our config from the .env file
import os

from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
ANTHROPIC_MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS", "500"))

MIDDLEWARE_HOST = os.getenv("MIDDLEWARE_HOST", "0.0.0.0")
MIDDLEWARE_PORT = int(os.getenv("MIDDLEWARE_PORT", "8000"))
