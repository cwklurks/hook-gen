from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Hook-Gen API", version="2.0.0")

# Manual CORS Middleware (Nuclear Option)
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

# Standard CORS (keep as backup)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.database import init_db

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/")
async def root():
    return {"message": "Hook-Gen API is running"}

from api import endpoints
app.include_router(endpoints.router)
