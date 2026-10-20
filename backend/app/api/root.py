from fastapi import APIRouter

router = APIRouter(tags=["root"])


@router.get("/")
def root() -> dict[str, str]:
    """The API's base URL: says the service is up and where its documentation is."""
    return {
        "message": "Equipment Rental Desk API is running",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }
