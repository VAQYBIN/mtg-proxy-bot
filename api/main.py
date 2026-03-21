from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routers import health
from bot.database import dispose_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await dispose_engine()


app = FastAPI(title="MTG Proxy API", lifespan=lifespan)

app.include_router(health.router)
