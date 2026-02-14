from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.db.session import create_db_and_tables
from app.api.v1.api import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    # Start background monitor
    import asyncio
    from app.services.scheduler import start_background_monitor
    asyncio.create_task(start_background_monitor())
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {"message": "GitHub Commit Collector API is running"}
