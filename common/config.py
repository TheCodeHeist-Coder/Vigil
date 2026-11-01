"""Settings for every service, read from the environment and .env."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

import common.net  # noqa: F401  # must apply before any network call

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    bench_id: str = os.getenv("BENCH_ID", "bench-1")
    kafka_bootstrap: str = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
    database_url: str = os.getenv("DATABASE_URL", "postgresql://yugabyte@localhost:5433/vigil")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    gemini_fallback_model: str = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.8-flash")
    gemini_embed_model: str = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-2")
    meko_api_key: str = os.getenv("MEKO_API_KEY", "")
    meko_mcp_url: str = os.getenv("MEKO_MCP_URL", "https://mcp.mekodata.ai/mcp")
    meko_datapack_name: str = os.getenv("MEKO_DATAPACK_NAME", "vigil-bench")
    replay: bool = os.getenv("REPLAY", "0") == "1"
    access_key: str = os.getenv("VIGIL_ACCESS_KEY", "")
    ingest_url: str = os.getenv("INGEST_URL", "http://localhost:8101")
    gateway_port: int = int(os.getenv("GATEWAY_PORT", "8100"))
    bind_host: str = os.getenv("BIND_HOST", "0.0.0.0")  # 127.0.0.1 behind a reverse proxy
    gateway_bind: str = os.getenv("GATEWAY_BIND", "")  # where a reverse proxy reaches the gateway
    webrtc_ports: str = os.getenv("WEBRTC_PORTS", "")  # like 40000-40099, for a narrow firewall


settings = Settings()
