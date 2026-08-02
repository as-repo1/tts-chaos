from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import router as voice_router
from backend.app.api.models_router import router as models_router
from backend.app.db.store import init_db

APP_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = APP_ROOT / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="TTS Chaos", version="1.0.0", lifespan=lifespan)
app.include_router(voice_router)
app.include_router(models_router)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")


@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    return HTMLResponse((FRONTEND_DIR / "index.html").read_text())
