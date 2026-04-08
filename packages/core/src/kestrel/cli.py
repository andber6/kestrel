"""CLI for managing Kestrel API keys and running the server."""

from __future__ import annotations

import argparse
import asyncio
import sys

from kestrel.auth.api_key import generate_api_key, hash_api_key, key_prefix


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="kestrel",
        description="Kestrel — Drop-in LLM API proxy that routes to the cheapest capable model",
        epilog="Documentation: https://github.com/andber6/kestrel",
    )
    parser.add_argument("--version", action="version", version="kestrel 0.1.0")
    sub = parser.add_subparsers(dest="command")

    # --- serve ---
    serve_parser = sub.add_parser("serve", help="Start the proxy server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    serve_parser.add_argument("--port", type=int, default=8080, help="Bind port")
    serve_parser.add_argument("--reload", action="store_true", help="Auto-reload on changes")

    # --- key generate ---
    key_parser = sub.add_parser("key", help="API key management")
    key_sub = key_parser.add_subparsers(dest="key_command")

    gen_parser = key_sub.add_parser("generate", help="Generate a new API key")
    gen_parser.add_argument("--name", required=True, help="Name for this key")
    gen_parser.add_argument(
        "--openai-key", default=None, help="Store an OpenAI API key with this key"
    )
    gen_parser.add_argument("--anthropic-key", default=None, help="Store an Anthropic API key")
    gen_parser.add_argument("--gemini-key", default=None, help="Store a Gemini API key")
    gen_parser.add_argument("--groq-key", default=None, help="Store a Groq API key")
    gen_parser.add_argument("--mistral-key", default=None, help="Store a Mistral API key")
    gen_parser.add_argument("--cohere-key", default=None, help="Store a Cohere API key")
    gen_parser.add_argument("--together-key", default=None, help="Store a Together AI API key")
    gen_parser.add_argument("--xai-key", default=None, help="Store an xAI API key")

    key_sub.add_parser("list", help="List all API keys")

    revoke_parser = key_sub.add_parser("revoke", help="Revoke an API key")
    revoke_parser.add_argument("key_prefix", help="Key prefix to revoke (e.g. ks-xxxxx...)")

    # --- logs ---
    logs_parser = sub.add_parser("logs", help="Request log management")
    logs_sub = logs_parser.add_subparsers(dest="logs_command")

    prune_parser = logs_sub.add_parser("prune", help="Delete old request logs")
    prune_parser.add_argument(
        "--older-than",
        required=True,
        help="Delete logs older than this duration (e.g. 30d, 7d, 24h)",
    )
    prune_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show how many rows would be deleted without deleting",
    )

    # --- migrate ---
    sub.add_parser("migrate", help="Run database migrations")

    args = parser.parse_args()

    if args.command == "serve":
        _cmd_serve(args)
    elif args.command == "key":
        if args.key_command == "generate":
            asyncio.run(_cmd_key_generate(args))
        elif args.key_command == "list":
            asyncio.run(_cmd_key_list())
        elif args.key_command == "revoke":
            asyncio.run(_cmd_key_revoke(args))
        else:
            key_parser.print_help()
    elif args.command == "logs":
        if args.logs_command == "prune":
            asyncio.run(_cmd_logs_prune(args))
        else:
            logs_parser.print_help()
    elif args.command == "migrate":
        _cmd_migrate()
    else:
        parser.print_help()


def _cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run(
        "kestrel.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


async def _cmd_key_generate(args: argparse.Namespace) -> None:
    from kestrel.config import Settings
    from kestrel.db.session import create_db_engine
    from kestrel.models.db import ApiKey

    try:
        settings = Settings()
        engine, session_factory = create_db_engine(settings.database_url)
    except Exception as e:
        print(f"Error: Could not connect to database: {e}")
        print("Set KS_DATABASE_URL or run 'kestrel migrate' first.")
        sys.exit(1)

    raw_key = generate_api_key()
    hashed = hash_api_key(raw_key)
    prefix = key_prefix(raw_key)

    from kestrel.auth.encryption import encrypt_value

    def _enc(val: str | None) -> str | None:
        return encrypt_value(val) if val else None

    async with session_factory() as session:
        record = ApiKey(
            key_hash=hashed,
            key_prefix=prefix,
            name=args.name,
            is_active=True,
            openai_api_key_encrypted=_enc(args.openai_key),
            anthropic_api_key_encrypted=_enc(args.anthropic_key),
            gemini_api_key_encrypted=_enc(args.gemini_key),
            groq_api_key_encrypted=_enc(args.groq_key),
            mistral_api_key_encrypted=_enc(args.mistral_key),
            cohere_api_key_encrypted=_enc(args.cohere_key),
            together_api_key_encrypted=_enc(args.together_key),
            xai_api_key_encrypted=_enc(args.xai_key),
        )
        session.add(record)
        await session.commit()

    await engine.dispose()

    print("API key generated successfully!")
    print(f"  Name:   {args.name}")
    print(f"  Key:    {raw_key}")
    print(f"  Prefix: {prefix}")
    print()
    print("Save this key — it cannot be retrieved later.")


async def _cmd_key_list() -> None:
    from sqlalchemy import select

    from kestrel.config import Settings
    from kestrel.db.session import create_db_engine
    from kestrel.models.db import ApiKey

    try:
        settings = Settings()
        engine, session_factory = create_db_engine(settings.database_url)
    except Exception as e:
        print(f"Error: Could not connect to database: {e}")
        print("Set KS_DATABASE_URL or run 'kestrel migrate' first.")
        sys.exit(1)

    async with session_factory() as session:
        result = await session.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
        keys = result.scalars().all()

    await engine.dispose()

    if not keys:
        print("No API keys found.")
        return

    print(f"{'Prefix':<15} {'Name':<30} {'Active':<8} {'Created'}")
    print("-" * 75)
    for k in keys:
        status = "yes" if k.is_active else "no"
        created = k.created_at.strftime("%Y-%m-%d %H:%M") if k.created_at else "—"
        print(f"{k.key_prefix:<15} {k.name:<30} {status:<8} {created}")


async def _cmd_key_revoke(args: argparse.Namespace) -> None:
    from sqlalchemy import select, update

    from kestrel.config import Settings
    from kestrel.db.session import create_db_engine
    from kestrel.models.db import ApiKey

    try:
        settings = Settings()
        engine, session_factory = create_db_engine(settings.database_url)
    except Exception as e:
        print(f"Error: Could not connect to database: {e}")
        print("Set KS_DATABASE_URL or run 'kestrel migrate' first.")
        sys.exit(1)

    async with session_factory() as session:
        result = await session.execute(select(ApiKey).where(ApiKey.key_prefix == args.key_prefix))
        key = result.scalar_one_or_none()

        if not key:
            print(f"No key found with prefix: {args.key_prefix}")
            await engine.dispose()
            sys.exit(1)

        await session.execute(update(ApiKey).where(ApiKey.id == key.id).values(is_active=False))
        await session.commit()

    await engine.dispose()
    print(f"Key revoked: {args.key_prefix} ({key.name})")


def _parse_duration(value: str) -> int:
    """Parse a duration string like '30d', '7d', '24h' into seconds."""
    value = value.strip().lower()
    if value.endswith("d"):
        return int(value[:-1]) * 86400
    if value.endswith("h"):
        return int(value[:-1]) * 3600
    if value.endswith("m"):
        return int(value[:-1]) * 60
    raise ValueError(f"Invalid duration: {value}. Use format like 30d, 24h, or 60m.")


async def _cmd_logs_prune(args: argparse.Namespace) -> None:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import delete, func, select

    from kestrel.config import Settings
    from kestrel.db.session import create_db_engine
    from kestrel.models.db import RequestLog

    try:
        seconds = _parse_duration(args.older_than)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    try:
        settings = Settings()
        engine, session_factory = create_db_engine(settings.database_url)
    except Exception as e:
        print(f"Error: Could not connect to database: {e}")
        sys.exit(1)

    cutoff = datetime.now(UTC) - timedelta(seconds=seconds)

    async with session_factory() as session:
        # Count rows to be deleted
        count_result = await session.execute(
            select(func.count()).select_from(RequestLog).where(RequestLog.created_at < cutoff)
        )
        count = count_result.scalar() or 0

        if count == 0:
            print(f"No request logs older than {args.older_than} found.")
            await engine.dispose()
            return

        if args.dry_run:
            print(f"[dry run] Would delete {count:,} request logs older than {args.older_than}.")
            await engine.dispose()
            return

        await session.execute(delete(RequestLog).where(RequestLog.created_at < cutoff))
        await session.commit()

    await engine.dispose()
    print(f"Deleted {count:,} request logs older than {args.older_than}.")


def _cmd_migrate() -> None:
    import subprocess

    subprocess.run(["alembic", "upgrade", "head"], check=True)


if __name__ == "__main__":
    main()
