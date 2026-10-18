"""The committed deployment files must wire in what start-up code and the README rely on.

These read the files; they do not start Docker, Render or Vercel. CI's `container` job is what runs
the real image (see .github/workflows/ci.yml).
"""

import json
import re
from pathlib import Path

import pytest
import yaml

from app.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def load_yaml(path: str) -> dict:
    return yaml.safe_load(read(path))


def instructions(dockerfile: str) -> list[tuple[str, str]]:
    """(INSTRUCTION, arguments) pairs, with comments dropped and continued lines joined."""
    joined = re.sub(r"\\\s*\n", " ", dockerfile)
    result = []
    for line in joined.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            keyword, _, rest = line.partition(" ")
            result.append((keyword.upper(), rest.strip()))
    return result


BACKEND = instructions(read("backend/Dockerfile"))


def last(keyword: str) -> str:
    return [rest for key, rest in BACKEND if key == keyword][-1]


# --- the backend image ---------------------------------------------------------------------------


def test_the_backend_image_starts_with_the_migrating_entry_point():
    assert json.loads(last("CMD")) == ["python", "-m", "app.serve"]


def test_the_backend_image_does_not_run_as_root():
    user = last("USER")

    assert user not in ("root", "0", "0:0")
    # The user is created before USER switches to it, and the code is owned by it.
    keywords = [key for key, _ in BACKEND]
    assert keywords.index("RUN") < keywords.index("USER")
    assert any(key == "COPY" and "--chown=app:app" in rest for key, rest in BACKEND)
    assert any(key == "RUN" and "useradd" in rest and "app" in rest for key, rest in BACKEND)


def test_the_backend_image_has_a_health_check_on_the_health_endpoint():
    healthcheck = last("HEALTHCHECK")

    assert json.loads(healthcheck[healthcheck.index("CMD") + 3 :]) == [
        "python",
        "-m",
        "app.healthcheck",
    ]
    # Start-up waits for the database and migrates before listening, so the first check must not
    # count against the container while that happens.
    start_period = int(re.search(r"--start-period=(\d+)s", healthcheck).group(1))
    assert start_period >= 60


def test_the_health_check_asks_the_port_the_server_listens_on():
    # Both honour PORT (Render sets it), and the health route exists.
    assert "PORT" in read("backend/app/serve.py")
    assert "PORT" in read("backend/app/healthcheck.py")
    assert '"/health"' in read("backend/app/api/health.py") or "/health" in read(
        "backend/app/api/health.py"
    )


# --- nothing may reset data automatically ---------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "backend/Dockerfile",
        "docker-compose.yml",
        "render.yaml",
        ".github/workflows/ci.yml",
    ],
)
def test_no_deployment_path_resets_the_database(path):
    text = read(path)

    assert "--reset" not in text
    assert "reset_and_seed" not in text
    assert "delete_all_rows" not in text


def test_the_reset_is_only_available_from_the_manual_command():
    serve = read("backend/app/serve.py")  # its docstring mentions the flag, so check the calls
    assert "reset_and_seed" not in serve
    assert "delete_all_rows" not in serve
    assert "--reset" in read("backend/app/db_setup.py")


# --- Render --------------------------------------------------------------------------------------


def render_service() -> dict:
    return load_yaml("render.yaml")["services"][0]


def render_variables() -> dict:
    return {entry["key"]: entry for entry in render_service()["envVars"]}


def test_render_runs_the_backend_image_and_checks_health():
    service = render_service()

    assert service["runtime"] == "docker"
    assert service["dockerfilePath"] == "./backend/Dockerfile"
    assert service["dockerContext"] == "./backend"
    assert service["healthCheckPath"] == "/health"
    # No startCommand: the image's CMD (app.serve) is what migrates and seeds.
    assert "dockerCommand" not in service
    assert "startCommand" not in service


def test_render_seeds_only_through_the_start_up_flag():
    assert render_variables()["SEED_ON_START"]["value"] == "true"


def test_render_takes_the_database_url_from_its_database_and_cors_from_the_dashboard():
    variables = render_variables()

    assert variables["DATABASE_URL"]["fromDatabase"]["name"] == "rental-desk-db"
    assert "value" not in variables["DATABASE_URL"]  # never a literal connection string
    assert variables["CORS_ORIGINS"]["sync"] is False  # set by hand, to the real UI origin
    assert "value" not in variables["CORS_ORIGINS"]


def test_render_blueprint_has_no_secret_looking_literals():
    for entry in render_variables().values():
        value = str(entry.get("value", ""))
        assert "://" not in value  # no URL with credentials baked in


# --- compose and the frontend ---------------------------------------------------------------------


def test_compose_passes_the_seed_flag_and_waits_for_a_healthy_backend():
    compose = load_yaml("docker-compose.yml")["services"]

    assert compose["backend"]["environment"]["SEED_ON_START"] == "${SEED_ON_START:-true}"
    assert compose["frontend"]["depends_on"]["backend"]["condition"] == "service_healthy"
    assert compose["backend"]["depends_on"]["db"]["condition"] == "service_healthy"


def test_the_hosted_frontend_has_the_test_clock_panel_off():
    # Compose builds it off unless someone turns it on in their own .env ...
    arguments = load_yaml("docker-compose.yml")["services"]["frontend"]["build"]["args"]
    assert arguments["VITE_ENABLE_TEST_CLOCK"] == "${VITE_ENABLE_TEST_CLOCK:-false}"
    # ... the Dockerfile defaults to off ...
    assert "ARG VITE_ENABLE_TEST_CLOCK=false" in read("frontend/Dockerfile")
    # ... and the example file for a Vercel or local build leaves it commented out.
    active = [
        line
        for line in read("frontend/.env.example").splitlines()
        if line.startswith("VITE_ENABLE_TEST_CLOCK")
    ]
    assert active == []


def test_vercel_serves_the_single_page_app_for_every_route():
    vercel = json.loads(read("frontend/vercel.json"))

    assert vercel["framework"] == "vite"
    assert {"source": "/(.*)", "destination": "/index.html"} in vercel["rewrites"]
    assert "try_files $uri /index.html" in read("frontend/nginx.conf")


# --- the example environment files stay complete --------------------------------------------------


def test_every_backend_setting_is_documented_in_the_example_environment():
    documented = {
        line.split("=", 1)[0].lstrip("# ").strip()
        for line in read(".env.example").splitlines()
        if "=" in line
    }

    for name in Settings.model_fields:
        assert name.upper() in documented, f"{name.upper()} is missing from .env.example"


def test_the_example_environment_has_no_real_looking_secrets():
    for line in read(".env.example").splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name in ("POSTGRES_PASSWORD",):
            assert value == "rental"  # the documented throwaway local value
        assert not re.search(r"(?i)(secret|token|api[_-]?key)", name)


# --- CI ------------------------------------------------------------------------------------------


def test_ci_runs_the_real_container_against_postgresql_and_the_frontend_tests():
    jobs = load_yaml(".github/workflows/ci.yml")["jobs"]
    container_steps = " ".join(str(step.get("run", "")) for step in jobs["container"]["steps"])
    frontend_steps = [str(step.get("run", "")) for step in jobs["frontend"]["steps"]]

    assert jobs["container"]["services"]["postgres"]["image"].startswith("postgres:")
    assert "docker compose config" in container_steps
    assert "docker build" in container_steps
    assert "docker restart api" in container_steps  # the restart-does-not-reseed check
    assert "npm test" in frontend_steps
