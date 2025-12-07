import logging
from fastapi import FastAPI, Request, Response

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Hook-Gen API", version="2.0.0")

# CORS: Handle preflight OPTIONS requests manually for maximum compatibility
@app.middleware("http")
async def cors_handler(request: Request, call_next):
    # Handle preflight OPTIONS request immediately
    if request.method == "OPTIONS":
        response = Response(status_code=200)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        response.headers["Access-Control-Max-Age"] = "86400"
        return response
    
    # Process the actual request
    response = await call_next(request)
    
    # Add CORS headers to all responses
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    
    return response

from app.database import init_db

@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("Application started successfully")

# Health check / root endpoint
@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {"message": "Hook-Gen API is running", "version": "2.0.0"}

@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok"}

# Include API routes
from api import endpoints
app.include_router(endpoints.router)
