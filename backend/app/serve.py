"""Container entry point: `python -m app.serve`.

Prepares the database, then runs the API in this same process (so it receives the container's stop
signal). The order matters: the API only starts listening once the schema is current.

1. Wait for the database to accept connections (a hosted database can lag behind the service).
2. `alembic upgrade head`: idempotent, changes no rows.
3. If SEED_ON_START is on, load the sample data only when the database is empty (`seed_if_empty`).
   Existing data is never touched and `--reset` is never used here.

If any step fails the process exits with an error and the API is not started, so a deployment with
a broken schema fails visibly instead of serving 500s.

Run a single instance. Two instances starting at the same moment are NOT handled: there is no lock.
Both could run the migration at once (one would normally fail on an already-created table and exit,
and succeed when restarted), and both could see an empty database and each load the sample data,
leaving it twice. A deploy that replaces a running instance is fine, since the old one finished
starting long before.
"""

import logging
import os
import time
from collections.abc import Callable

import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

from app import db_setup
from app.config import get_settings
from app.db import make_engine

logger = logging.getLogger("app.serve")

CONNECT_ATTEMPTS = 10
CONNECT_DELAY_SECONDS = 3.0


def wait_for_database(
    attempts: int = CONNECT_ATTEMPTS,
    delay: float = CONNECT_DELAY_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Return once a connection works; raise the last error after `attempts` tries.

    Only the error's class is logged: a connection error's text can include the host and user.
    """
    for attempt in range(1, attempts + 1):
        engine = make_engine()
        try:
            with engine.connect() as connection:
                connection.execute(sa.text("SELECT 1"))
            return
        except OperationalError as error:
            if attempt == attempts:
                raise
            logger.warning(
                "Database not reachable yet (%s), attempt %d of %d",
                type(error).__name__,
                attempt,
                attempts,
            )
            sleep(delay)
        finally:
            engine.dispose()


def prepare_database(*, seed: bool) -> None:
    wait_for_database()
    db_setup.run_migrations()
    if seed:
        db_setup.seed_if_empty()
    else:
        logger.info("SEED_ON_START is off; not loading sample data")


def main() -> None:
    prepare_database(seed=get_settings().seed_on_start)

    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    main()
