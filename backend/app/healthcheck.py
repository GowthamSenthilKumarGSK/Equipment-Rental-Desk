"""Container health check: `python -m app.healthcheck`. Exits 0 when GET /health answers 200.

Used by the Dockerfile's HEALTHCHECK. The slim Python image has no curl, so this uses the standard
library. It asks the server on the same port the server listens on (PORT, default 8000).
"""

import os
import sys
import urllib.request


def is_healthy(port: int, timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=timeout) as response:
            return response.status == 200
    except OSError:
        # Refused, timed out, or an HTTP error status (urllib's HTTPError is an OSError).
        return False


def main() -> None:
    sys.exit(0 if is_healthy(int(os.environ.get("PORT", "8000"))) else 1)


if __name__ == "__main__":
    main()
