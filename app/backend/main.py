import argparse
import logging
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent


def _setup_logging() -> None:
    level = getattr(logging, os.environ.get("LOG_LEVEL", "info").upper(), logging.INFO)
    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    handlers: list[logging.Handler] = [logging.StreamHandler()]

    # Rolling file log so we can look back at what happened (queries, kiosk
    # events, errors). 5 MB x 5 files; path is LOG_FILE (in Docker it points
    # at the persistent /data volume).
    log_file = os.environ.get("LOG_FILE", "app.log")
    try:
        from logging.handlers import RotatingFileHandler

        log_path = Path(log_file)
        if log_path.parent != Path("."):
            log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=5)
        )
    except OSError:
        logging.getLogger(__name__).warning("cannot open log file %s; console only", log_file)

    for h in handlers:
        h.setFormatter(fmt)
    logging.basicConfig(level=level, handlers=handlers)


def run_api(host: str = "0.0.0.0", port: int = 8000, reload: bool = False) -> None:
    import uvicorn

    uvicorn.run(
        "src.presentation.api:app",
        host=host,
        port=port,
        reload=reload,
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
        # Let uvicorn's server + access logs propagate to the root logger so
        # they land in the rotating file as well as the console.
        log_config=None,
    )


def run_migrate() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(ROOT_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT_DIR / "alembic"))
    command.upgrade(cfg, "head")


def run_seed_agencies(csv_path: Path | None = None) -> tuple[int, int]:
    from src.infrastructure.seeds.agency_seeder import seed_agencies

    cats, agencies = seed_agencies(csv_path)
    logging.getLogger("talkbox.seed").info(
        "seed-agencies complete: %d categories, %d agencies", cats, agencies
    )
    return cats, agencies


def run_seed() -> None:
    """Full bootstrap: alembic + vector seeds + agencies seeds."""
    run_migrate()

    from src.infrastructure.seeds.vector_seeder import seed_query_categories

    n = seed_query_categories()
    logging.getLogger("talkbox.seed").info("vector seed complete: %d documents", n)

    run_seed_agencies()


def main() -> None:
    _setup_logging()

    parser = argparse.ArgumentParser(prog="talkbox")
    sub = parser.add_subparsers(dest="command", required=True)

    api_cmd = sub.add_parser("api", help="Run the FastAPI HTTP server")
    api_cmd.add_argument("--host", default=os.environ.get("API_HOST", "0.0.0.0"))
    api_cmd.add_argument("--port", type=int, default=int(os.environ.get("API_PORT", "8000")))
    api_cmd.add_argument("--reload", action="store_true")

    sub.add_parser("migrate", help="Run pending Alembic migrations (alembic upgrade head)")
    sub.add_parser(
        "seed",
        help="Full bootstrap: migrate + vector seeds + agencies/categories seeds",
    )

    seed_ag_cmd = sub.add_parser(
        "seed-agencies",
        help="Reload categories + agencies tables from the master CSV (idempotent)",
    )
    seed_ag_cmd.add_argument(
        "--csv",
        default=None,
        help="Override the default CSV path (packaged under src/infrastructure/seeds/)",
    )

    args = parser.parse_args()
    if args.command == "api":
        run_api(host=args.host, port=args.port, reload=args.reload)
    elif args.command == "migrate":
        run_migrate()
    elif args.command == "seed":
        run_seed()
    elif args.command == "seed-agencies":
        run_seed_agencies(Path(args.csv).resolve() if args.csv else None)


if __name__ == "__main__":
    main()
