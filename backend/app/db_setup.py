"""Migrate and seed in one repeatable command: `python -m app.db_setup [--reset]`.

- Always runs `alembic upgrade head` (a no-op when the schema is current).
- Seeds only an empty database, so running it twice never duplicates data.
- `--reset` wipes all rows first (the schema is kept) and seeds again.
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reset", action="store_true", help="delete all rows, then re-seed")
    args = parser.parse_args()

    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    # Alembic's env.py applies alembic.ini's logging config, so ours is set up after it runs.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    logger.info("Migrations are up to date")

    engine = make_engine()
    with session_scope(engine) as session:
        if args.reset:
            delete_all_rows(session)
            logger.warning("Deleted all rows because --reset was given")
        if seed_database(session, SystemClock().now()):
            logger.info("Seeded sample data")
        else:
            logger.info("Database already has data; seeding skipped (use --reset to start over)")
    engine.dispose()


if __name__ == "__main__":
    main()
