"""Knowledge Base Search Engine - FastAPI Application"""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routes import documents_router, queries_router
from app.models import Base
from sqlalchemy import create_engine

STATIC_DIR = Path(__file__).parent / "static"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Knowledge Base Search with Hybrid Retrieval and LLM Integration",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
engine = create_engine(settings.database_url)
Base.metadata.create_all(bind=engine)
logger.info(f"Database initialized: {settings.database_url}")

# Register routers
app.include_router(documents_router)
app.include_router(queries_router)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/ui")
async def search_ui():
    """Search UI for connecting to the API"""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "operational",
        "service": settings.app_name,
        "version": settings.app_version
    }

@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "endpoints": {
            "ui": "/ui",
            "docs": "/api/docs",
            "health": "/health",
            "upload": "/api/documents/upload",
            "search": "/api/queries/search",
            "search_stream": "/api/queries/search/stream",
            "analytics": "/api/queries/analytics",
        },
    }

@app.on_event("startup")
async def startup_event():
    """Application startup tasks"""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Embedding provider: {settings.embedding_provider}")
    logger.info(f"LLM provider: {settings.llm_provider}")
    logger.info(f"Reranking enabled: {settings.rerank_enabled}")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown tasks"""
    logger.info(f"Shutting down {settings.app_name}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
