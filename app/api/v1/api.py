from fastapi import APIRouter
from app.api.v1.endpoints import collectors, history

api_router = APIRouter()
api_router.include_router(collectors.router, prefix="/collect", tags=["collection"])
api_router.include_router(history.router, prefix="/history", tags=["history"])
