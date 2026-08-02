import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import router as voice_router
from backend.app.api.models_router import router as models_router
from backend.app.db.store import init_db
from backend.app.services.model_manager import model_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("tts-chaos")

APP_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = APP_ROOT / "frontend"
_START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("TTS Chaos starting up...")
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("TTS Chaos shutting down")


app = FastAPI(title="TTS Chaos", version="2.0.0", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(voice_router)
app.include_router(models_router)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")


@app.get("/api/system/info")
async def system_info():
    disk = model_manager.get_disk_usage()
    installed = model_manager.list_installed()
    uptime = int(time.time() - _START_TIME)
    return {
        "version": "2.0.0",
        "uptime_seconds": uptime,
        "installed_models": len(installed),
        "installed_model_ids": [m.model_id for m in installed],
        "disk": disk,
    }


@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    return HTMLResponse((FRONTEND_DIR / "index.html").read_text())
