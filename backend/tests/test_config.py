import pytest

from app.config import Settings


@pytest.mark.parametrize(
    "raw",
    [
        "postgres://u:p@host:5432/db",
        "postgresql://u:p@host:5432/db",
        "postgresql+psycopg://u:p@host:5432/db",
    ],
)
def test_sqlalchemy_url_always_uses_psycopg_driver(raw):
    settings = Settings(database_url=raw)

    assert settings.sqlalchemy_url == "postgresql+psycopg://u:p@host:5432/db"


def test_cors_origins_are_split_and_trimmed():
    settings = Settings(cors_origins=" http://a.test , http://b.test ,")

    assert settings.cors_origin_list == ["http://a.test", "http://b.test"]
