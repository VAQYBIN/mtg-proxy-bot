from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.routers import admin, auth, health, proxies, pub_settings, users
from bot.database import dispose_engine

UPLOADS_DIR = Path("/app/uploads")


@asynccontextmanager
async def lifespan(app: FastAPI):
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    yield
    await dispose_engine()


app = FastAPI(title="MTG Proxy API", lifespan=lifespan)

app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(proxies.router)
app.include_router(pub_settings.router)
app.include_router(admin.router)
