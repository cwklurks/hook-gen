import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

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

@app.on_event("startup")
def on_startup():
    init_db()

# Health check endpoint
@app.get("/health")
async def health():
    return {"status": "ok"}

# Include API routes FIRST (they take priority over static files)
from api import endpoints
app.include_router(endpoints.router)

# Serve static files from the 'static' directory (built Next.js output)
# This is mounted last so API routes take priority
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    # Serve static files with html=True to handle index.html automatically
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
