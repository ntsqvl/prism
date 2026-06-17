from pydantic_settings import BaseSettings
from pathlib import Path
from dotenv import load_dotenv
import os

# Load environment variables from .env (ensure settings pick them up)
load_dotenv()


class Settings(BaseSettings):
    UPLOAD_DIR: str = str(Path.cwd() / "uploads")
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    CONTEXT_SAMPLE_CHUNKS: int = 100
    CONTEXT_CONFIDENCE_THRESHOLD: float = 0.8
    # AI/ML / OpenAI settings
    AIML_API_KEY: str | None = None
    AIML_BASE_URL: str = "https://api.openai.com/v1"
    AIML_EMBEDDING_MODEL: str = "text-embedding-3-small"
    MAX_EMBEDDING_RETRIES: int = 3

    # Featherless / other agent provider (context discovery)
    FEATHERLESS_API_KEY: str | None = None
    FEATHERLESS_BASE_URL: str | None = None
    FEATHERLESS_MODEL: str | None = None

    # Backwards-compatible OpenAI aliases
    OPENAI_API_KEY: str | None = None
    OPENAI_API_BASE: str | None = None

    # Batch Config
    CONTEXT_BATCH_SIZE: int = 15


settings = Settings()
# Allow OPENAI_* env vars to populate AIML settings if present
if os.getenv("OPENAI_API_KEY") and not settings.AIML_API_KEY:
    settings.AIML_API_KEY = os.getenv("OPENAI_API_KEY")
if os.getenv("OPENAI_API_BASE") and settings.AIML_BASE_URL == "https://api.openai.com/v1":
    settings.AIML_BASE_URL = os.getenv("OPENAI_API_BASE")
