"""main.py - Inisialisasi FastAPI dan registrasi router."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

import database as db
from routes import resource, transaction


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()  # buat tabel bila belum ada
    yield


app = FastAPI(title="API Perpustakaan - UTS Komputasi Paralel dan Terdistribusi", lifespan=lifespan)
app.include_router(resource.router)
app.include_router(transaction.router)


@app.get("/", tags=["Root"])
async def root():
    return {"message": "API Perpustakaan aktif", "docs": "/docs", "use_lock": db.USE_LOCK}
