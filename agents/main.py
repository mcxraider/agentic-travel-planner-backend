"""
FastAPI application entry point.

Assembles the FastAPI app with all agent routers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents.clarification.clarification_api import router as clarification_router


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
                "status": "planned",
            },
            "planner": {
                "status": "planned",
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
