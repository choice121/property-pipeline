import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

from routers import health, scraper, properties, images, publisher, download, search, ai, sync, live_images, stats

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "storage", "images"), exist_ok=True)


async def _background_sync_loop():
    await asyncio.sleep(30)
    while True:
        try:
            from services import setup_service
            from database.repository import Repository
            from services import live_sync_service

            # Run blocking I/O in a thread so the event loop stays responsive
            readiness = await asyncio.to_thread(setup_service.get_setup_status)
            if not readiness["core_ready"]:
                logger.warning("Background sync skipped: %s", readiness["summary"])
                await asyncio.sleep(300)
                continue

            repo = Repository()
            await asyncio.to_thread(live_sync_service.sync_from_live, repo)
        except Exception as e:
            logger.error("Background sync error: %s", e)
        await asyncio.sleep(300)  # Wait 5 minutes between syncs


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_background_sync_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Property Pipeline API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(scraper.router, prefix="/api")
app.include_router(properties.router, prefix="/api")
app.include_router(images.router, prefix="/api")
app.include_router(publisher.router, prefix="/api")
app.include_router(download.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(sync.router, prefix="/api")
app.include_router(live_images.router, prefix="/api")
app.include_router(stats.router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("BACKEND_PORT", 8000))
    reload = os.getenv("BACKEND_RELOAD", "true").lower() == "true"
    uvicorn.run("main:app", host=host, port=port, reload=reload)
