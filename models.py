"""models.py - Skema Pydantic (request dan response)."""
from typing import Literal

from pydantic import BaseModel, Field

TrxStatus = Literal["pending", "processing", "completed", "failed"]


class BookCreate(BaseModel):
    judul: str = Field(..., min_length=1, max_length=200)
    penulis: str = Field(..., min_length=1, max_length=100)
    kategori: str = Field(..., min_length=1, max_length=50)
    tahun_terbit: int = Field(..., ge=1000, le=2100)
    stok: int = Field(..., ge=0)


class BookOut(BaseModel):
    # Response tidak membatasi stok >= 0 agar stok negatif (overselling Tahap 1) tetap terbaca
    id: int
    judul: str
    penulis: str
    kategori: str
    tahun_terbit: int
    stok: int


class TransactionCreate(BaseModel):
    item_id: int = Field(..., gt=0, description="ID buku yang dipinjam")
    qty: int = Field(..., gt=0, description="Jumlah eksemplar")
    peminjam: str = Field("anonim", min_length=1, max_length=100)


class TransactionOut(BaseModel):
    id: int
    item_id: int
    qty: int
    peminjam: str
    status: TrxStatus
    created_at: str
    updated_at: str


class TransactionAccepted(BaseModel):
    id: int
    status: TrxStatus
    message: str
