from fastapi import FastAPI

from backend.api.routes.health import router as health_router


app = FastAPI(title="yolo-platform")
app.include_router(health_router, prefix="/api")
