"""
FastAPI application entry point.

Assembles the FastAPI app with all agent routers.
"""

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents.clarification.clarification_api import router as clarification_router
from agents.graph.orchestrator_api import router as orchestrator_router


# ============================================================================
# Logging configuration (single source of truth for all agents)
# ============================================================================
LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)-35s | %(message)s"
)

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,  # Override any prior basicConfig calls
)

# Quiet noisy third-party loggers
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)


# Create FastAPI app
app = FastAPI(
    title="Trippi",
    description="AI-powered trip planning agents built with LangGraph",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(clarification_router)
app.include_router(orchestrator_router)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Trippi",
        "version": "0.1.0",
        "agents": {
            "clarification": {
                "status": "active",
                "endpoints": "/api/clarification",
            },
            "research": {
                "status": "active (mock)",
                "endpoints": "/api/orchestrator",
            },
            "planner": {
                "status": "active (mock)",
                "endpoints": "/api/orchestrator",
            },
            "orchestrator": {
                "status": "active",
                "endpoints": "/api/orchestrator",
            },
            "validator": {
                "status": "planned",
            },
        },
    }


@app.get("/health")
async def health():
    """Global health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
