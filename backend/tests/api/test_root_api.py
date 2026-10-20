"""The API's base URL answers with a friendly pointer to the documentation."""

from tests.api.conftest import error_code


def test_the_base_url_says_the_api_is_running_and_where_the_docs_are(api):
    response = api.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "message": "Equipment Rental Desk API is running",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


def test_the_links_it_gives_really_work(api):
    links = api.get("/").json()

    docs = api.get(links["docs"])
    openapi = api.get(links["openapi"])

    assert docs.status_code == 200
    assert "text/html" in docs.headers["content-type"]
    assert openapi.status_code == 200
    assert openapi.json()["info"]["title"] == "Equipment Rental Desk API"


def test_the_base_url_works_without_a_test_clock_and_carries_a_request_id(api):
    response = api.get("/", at=None)

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]


def test_the_base_url_is_read_only_and_other_methods_use_the_standard_error(api):
    response = api.post("/")

    assert (response.status_code, error_code(response)) == (405, "method_not_allowed")
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


def test_unknown_paths_still_get_the_standard_not_found_error(api):
    response = api.get("/nope")

    assert (response.status_code, error_code(response)) == (404, "route_not_found")
