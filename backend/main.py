import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Hook-Gen API", version="2.0.0")

# CORS middleware for local development (harmless in production since same-origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.database import init_db

# Determine static directory path
static_dir = os.path.join(os.path.dirname(__file__), "static")
logger.info(f"Static directory path: {static_dir}")
logger.info(f"Static directory exists: {os.path.exists(static_dir)}")
if os.path.exists(static_dir):
    logger.info(f"Static directory contents: {os.listdir(static_dir)[:10]}")

@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("Application started successfully")

# Health check endpoint
@app.get("/health")
async def health():
    return {"status": "ok"}

# Include API routes FIRST (they take priority over static files)
from api import endpoints
app.include_router(endpoints.router)

# Serve static files from the 'static' directory (built Next.js output)
if os.path.exists(static_dir):
    # Serve index.html for the root path explicitly
    index_path = os.path.join(static_dir, "index.html")
    
    @app.get("/", response_class=HTMLResponse)
    async def serve_root():
        logger.info("Serving root index.html")
        if os.path.exists(index_path):
            with open(index_path, "r") as f:
                return HTMLResponse(content=f.read())
        return HTMLResponse(content="<h1>Index not found</h1>", status_code=404)
    
    # Mount static files for assets (JS, CSS, etc.) at /_next
    next_static = os.path.join(static_dir, "_next")
    if os.path.exists(next_static):
        app.mount("/_next", StaticFiles(directory=next_static), name="next_static")
    
    # Mount for other static assets
    app.mount("/static", StaticFiles(directory=static_dir), name="static_assets")
else:
    @app.get("/")
    async def no_static():
        return {"error": "Static files not found", "path": static_dir}
