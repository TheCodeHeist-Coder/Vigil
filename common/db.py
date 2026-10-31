"""YugabyteDB connections. It speaks the PostgreSQL protocol."""

import psycopg

from common.config import settings


def connect() -> psycopg.Connection:
    return psycopg.connect(settings.database_url, autocommit=True)


def vector(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"
