"""Settings for every service, read from the environment and .env."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    bench_id: str = os.getenv("BENCH_ID", "bench-1")
    kafka_bootstrap: str = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
    database_url: str = os.getenv("DATABASE_URL", "postgresql://yugabyte@localhost:5433/vigil")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    gemini_embed_model: str = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-2")
    meko_api_key: str = os.getenv("MEKO_API_KEY", "")
    meko_mcp_url: str = os.getenv("MEKO_MCP_URL", "https://mcp.mekodata.ai/mcp")
    meko_datapack_name: str = os.getenv("MEKO_DATAPACK_NAME", "vigil-bench")
    replay: bool = os.getenv("REPLAY", "0") == "1"


settings = Settings()
