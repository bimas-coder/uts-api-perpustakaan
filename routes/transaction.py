"""routes/transaction.py - Endpoint transaksi peminjaman dengan async processing."""
import asyncio
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

import database as db
from models import TransactionAccepted, TransactionCreate, TransactionOut, TrxStatus

router = APIRouter(prefix="/transactions", tags=["Transaksi"])


async def proses_transaksi_background(trx_id: int, item_id: int, qty: int) -> None:
    """Fungsi pekerja internal (BUKAN endpoint HTTP).

    Dijalankan FastAPI setelah respon dikirim. Karena memakai async/await,
    saat menunggu I/O (sleep / query DB) event loop bebas melayani request lain.
    """
    try:
        # 1. pending -> processing
        await db.update_trx_status(trx_id, "processing")
        # 2. Simulasi pekerjaan I/O intensif (non-blocking, tidak menahan event loop)
        await asyncio.sleep(3)
        # 3. processing -> completed
        await db.update_trx_status(trx_id, "completed")
    except Exception:
        # Gagal: tandai failed dan kembalikan stok yang sudah dipotong
        await db.update_trx_status(trx_id, "failed")
        await db.restore_stok(item_id, qty)


@router.post("", response_model=TransactionAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_transaction(data: TransactionCreate, bg: BackgroundTasks):
    # Validasi: buku harus terdaftar
    if await db.get_book(data.item_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Buku tidak ditemukan")

    # Potong stok di critical section (dilindungi asyncio.Lock jika USE_LOCK=1).
    # Dilakukan sebelum respon agar request yang kalah balapan langsung ditolak 409.
    if not await db.potong_stok(data.item_id, data.qty):
        raise HTTPException(status.HTTP_409_CONFLICT, "Stok habis atau tidak mencukupi")

    trx_id = await db.insert_transaction(data.item_id, data.qty, data.peminjam, status="pending")

    # Jadwalkan pemrosesan latar belakang; respon langsung dikembalikan tanpa menunggu
    bg.add_task(proses_transaksi_background, trx_id, data.item_id, data.qty)
    return {"id": trx_id, "status": "pending", "message": "Transaksi diproses"}


@router.get("", response_model=list[TransactionOut], status_code=status.HTTP_200_OK)
async def list_transactions(
    status_filter: Optional[TrxStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
):
    return await db.list_transactions(status_filter, skip, limit)


@router.get("/{trx_id}", response_model=TransactionOut, status_code=status.HTTP_200_OK)
async def get_transaction(trx_id: int):
    trx = await db.get_transaction(trx_id)
    if not trx:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaksi tidak ditemukan")
    return trx
