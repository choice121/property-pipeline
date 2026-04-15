import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from routers import health, scraper, properties, images, publisher, download, search

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "storage", "images"), exist_ok=True)

app = FastAPI(title="Property Pipeline API")

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

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("BACKEND_PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
