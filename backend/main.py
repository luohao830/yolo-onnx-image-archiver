from fastapi import FastAPI

from backend.api.routes.health import router as health_router
from backend.api.routes.public_jobs import router as public_jobs_router


app = FastAPI(title="yolo-platform")
app.include_router(health_router, prefix="/api")
app.include_router(public_jobs_router, prefix="/api")
