from fastapi import APIRouter


router = APIRouter(tags=["health"])

HEALTH_STATUS_OK = "ok"


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": HEALTH_STATUS_OK}
