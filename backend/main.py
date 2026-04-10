import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from database.db import init_db
from routers import health, scraper, properties, images, publisher, download, search

app = FastAPI(title="Property Pipeline API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

app.include_router(health.router, prefix="/api")
app.include_router(scraper.router, prefix="/api")
app.include_router(properties.router, prefix="/api")
app.include_router(images.router, prefix="/api")
app.include_router(publisher.router, prefix="/api")
app.include_router(download.router, prefix="/api")
app.include_router(search.router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
