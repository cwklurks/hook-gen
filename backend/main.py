from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Hook-Gen API", version="2.0.1")

# Configure CORS
# Using allow_origin_regex to safely allow all with credentials
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex="https?://.*",  # Allow any http/https origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.database import init_db

@app.on_event("startup")
def on_startup():
    logger.info("Starting up Hook-Gen API...")
    init_db()

@app.get("/")
async def root():
    return {"message": "Hook-Gen API is running", "version": "2.0.1"}

# Global exception handler for debugging
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": str(exc)},
    )

from api import endpoints
app.include_router(endpoints.router)
