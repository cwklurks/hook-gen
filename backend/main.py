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
    all_files = os.listdir(static_dir)
    logger.info(f"Static directory contents ({len(all_files)} items): {all_files}")
    # Check for index.html in various locations
    index_locations = [
        os.path.join(static_dir, "index.html"),
        os.path.join(static_dir, "index", "index.html"),
    ]
    for loc in index_locations:
        logger.info(f"Checking {loc}: exists={os.path.exists(loc)}")

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
    # Find index.html - could be at root or in index/ folder (depending on trailingSlash)
    index_path = os.path.join(static_dir, "index.html")
    if not os.path.exists(index_path):
        index_path = os.path.join(static_dir, "index", "index.html")
    
    logger.info(f"Using index path: {index_path}, exists: {os.path.exists(index_path)}")
    
    @app.get("/", response_class=HTMLResponse)
    async def serve_root():
        logger.info(f"Serving root, index_path={index_path}")
        if os.path.exists(index_path):
            with open(index_path, "r") as f:
                return HTMLResponse(content=f.read())
        # List what's actually in static dir for debugging
        files = os.listdir(static_dir) if os.path.exists(static_dir) else []
        return HTMLResponse(
            content=f"<h1>Index not found</h1><p>Looking for: {index_path}</p><p>Available files: {files}</p>",
            status_code=404
        )
    
    # Mount static files for assets (JS, CSS, etc.) at /_next
    next_static = os.path.join(static_dir, "_next")
    if os.path.exists(next_static):
        app.mount("/_next", StaticFiles(directory=next_static), name="next_static")
    
    # Mount for other static assets (images, svgs, etc.)
    app.mount("/assets", StaticFiles(directory=static_dir), name="static_assets")
else:
    @app.get("/")
    async def no_static():
        return {"error": "Static files not found", "path": static_dir}
