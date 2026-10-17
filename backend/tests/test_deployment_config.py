"""The ALLOW_TEST_CLOCK switch must actually reach every place the API runs.

A setting that is read by the code but never passed to the container does nothing, which is exactly
how `ALLOW_TEST_CLOCK=false` failed to work under Docker Compose before. These tests read the
committed config files, so that cannot happen silently again. They do not start Docker or Render.
"""

from pathlib import Path

import pytest
import yaml

from app.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_yaml(name: str) -> dict:
    return yaml.safe_load((REPO_ROOT / name).read_text(encoding="utf-8"))


def test_docker_compose_passes_allow_test_clock_to_the_backend():
    environment = load_yaml("docker-compose.yml")["services"]["backend"]["environment"]

    # Taken from the host's .env when set, and on (the documented reviewer default) when not.
    assert environment["ALLOW_TEST_CLOCK"] == "${ALLOW_TEST_CLOCK:-true}"


def test_render_blueprint_sets_allow_test_clock_explicitly():
    service = load_yaml("render.yaml")["services"][0]
    variables = {entry["key"]: entry for entry in service["envVars"]}

    assert variables["ALLOW_TEST_CLOCK"]["value"] == "true"  # a string, as Render env vars are


def test_env_example_documents_allow_test_clock():
    lines = (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()

    assert "ALLOW_TEST_CLOCK=true" in lines


@pytest.mark.parametrize(
    ("value", "expected"), [("false", False), ("False", False), ("0", False), ("true", True)]
)
def test_the_setting_is_read_from_the_environment(monkeypatch, value, expected):
    monkeypatch.setenv("ALLOW_TEST_CLOCK", value)

    assert Settings(_env_file=None).allow_test_clock is expected


def test_the_test_clock_is_allowed_when_nothing_is_set(monkeypatch):
    monkeypatch.delenv("ALLOW_TEST_CLOCK", raising=False)

    assert Settings(_env_file=None).allow_test_clock is True
