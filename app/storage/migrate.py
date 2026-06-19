from __future__ import annotations

from pathlib import Path

import psycopg

from app.core.config import AppConfig, get_config


MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def run_migrations(config: AppConfig | None = None) -> None:
    """
    Apply all pending SQL migrations to the database referenced by POSTGRES_URL.

    NOTE: The target database must already exist; this function will not create it.
    """
    config = config or get_config()
    dsn = config.postgres_url

    async with await psycopg.AsyncConnection.connect(dsn) as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version    TEXT        PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )

        async with conn.cursor() as cur:
            await cur.execute("SELECT version FROM schema_migrations")
            applied = {row[0] for row in await cur.fetchall()}

        migration_files = sorted(
            f for f in MIGRATIONS_DIR.iterdir() if f.is_file() and f.suffix == ".sql"
        )

        for path in migration_files:
            version = path.name
            if version in applied:
                continue

            sql_text = path.read_text(encoding="utf-8")
            async with conn.transaction():
                await conn.execute(sql_text)
                await conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    (version,),
                )
            print(f"Applied migration: {version}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_migrations())
