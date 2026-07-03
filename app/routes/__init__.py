"""Routes package - API endpoints"""
from app.routes.documents import router as documents_router
from app.routes.queries import router as queries_router

__all__ = [
    "documents_router",
    "queries_router",
]
