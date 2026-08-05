import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import router as voice_router
from backend.app.api.models_router import router as models_router
from backend.app.api.stream_router import router as stream_router
from backend.app.db.store import init_db
from backend.app.services.model_manager import model_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("tts-chaos")

APP_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = APP_ROOT / "frontend"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "2002"))
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "true").lower() == "true"
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:2002,http://127.0.0.1:2002",
    ).split(",")
    if origin.strip()
]
_START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("TTS Chaos starting up...")
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("TTS Chaos shutting down")


app = FastAPI(
    title="TTS Chaos",
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
)

from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(voice_router)
app.include_router(models_router)
app.include_router(stream_router)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")


@app.get("/api/system/info")
async def system_info():
    disk = model_manager.get_disk_usage()
    installed = model_manager.list_installed()
    uptime = int(time.time() - _START_TIME)
    return {
        "version": "1.1.0",
        "uptime_seconds": uptime,
        "installed_models": len(installed),
        "installed_model_ids": [m.model_id for m in installed],
        "disk": disk,
    }


@app.get("/{full_path:path}", response_class=HTMLResponse)
def serve_frontend(full_path: str):
    if full_path.startswith("api/") or full_path.startswith("static/"):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    html_path = FRONTEND_DIR / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Frontend not built or missing index.html</h1>", status_code=404)
    return HTMLResponse(html_path.read_text())
