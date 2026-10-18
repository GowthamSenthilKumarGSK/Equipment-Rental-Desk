"""Migrate and seed in one repeatable command: `python -m app.db_setup [--reset]`.

- Always runs `alembic upgrade head` (a no-op when the schema is current).
- Seeds only an empty database, so running it twice never duplicates data.
- `--reset` wipes all rows first (the schema is kept) and seeds again. Only a person typing the flag
  does this: the container start-up (`app.serve`) never passes it.

The same steps are available as functions so that start-up can run them without the command line.
"""

import argparse
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.clock import SystemClock
from app.db import make_engine, session_scope
from app.seed import delete_all_rows, seed_database

logger = logging.getLogger("app.db_setup")

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def run_migrations() -> None:
    """Bring the schema up to date. Safe to repeat; changes no rows."""
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    # Alembic's env.py applies alembic.ini's logging config, so ours is set up after it runs.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    logger.info("Migrations are up to date")


def seed_if_empty() -> bool:
    """Load the sample data only when the database has no members or items. Never deletes."""
    engine = make_engine()
    try:
        with session_scope(engine) as session:
            seeded = seed_database(session, SystemClock().now())
    finally:
        engine.dispose()
    if seeded:
        logger.info("Seeded sample data")
    else:
        logger.info("Database already has data; seeding skipped (use --reset to start over)")
    return seeded


def reset_and_seed() -> None:
    """Delete every row, then load the sample data again. Destructive; only for a person to ask."""
    engine = make_engine()
    try:
        with session_scope(engine) as session:
            delete_all_rows(session)
            logger.warning("Deleted all rows because --reset was given")
            seed_database(session, SystemClock().now())
    finally:
        engine.dispose()
    logger.info("Seeded sample data")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reset", action="store_true", help="delete all rows, then re-seed")
    args = parser.parse_args()

    run_migrations()
    if args.reset:
        reset_and_seed()
    else:
        seed_if_empty()


if __name__ == "__main__":
    main()
