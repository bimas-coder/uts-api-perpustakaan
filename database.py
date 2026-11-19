"""database.py - Koneksi aiosqlite, inisialisasi tabel, dan fungsi pemotongan stok."""
import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import aiosqlite

DB_PATH = os.getenv("DB_PATH", "perpustakaan.db")

# Mode uji race condition: USE_LOCK=0 -> tanpa lock (Tahap 1), USE_LOCK=1 -> dengan lock (Tahap 2)
USE_LOCK = os.getenv("USE_LOCK", "1") == "1"

# Gembok konkurensi tingkat modul.
# CATATAN: asyncio.Lock hanya berlaku di dalam SATU proses (satu event loop).
# Pada multi-worker, setiap worker punya lock sendiri, sehingga decrement_stok_atomic
# (UPDATE ... WHERE stok >= qty) dipakai sebagai pengaman tambahan di level database.
stok_lock = asyncio.Lock()

CREATE_BOOKS_TABLE = """
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    judul TEXT NOT NULL,
    penulis TEXT NOT NULL,
    kategori TEXT NOT NULL,
    tahun_terbit INTEGER NOT NULL,
    stok INTEGER NOT NULL            -- kolom kuantitas wajib (tanpa CHECK agar overselling Tahap 1 bisa terlihat)
);
"""

CREATE_TRANSACTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    qty INTEGER NOT NULL,
    peminjam TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


@asynccontextmanager
async def get_conn():
    """Satu koneksi aiosqlite per operasi (non-blocking)."""
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        db.row_factory = aiosqlite.Row
        yield db


async def init_db() -> None:
    async with get_conn() as db:
        await db.execute("PRAGMA journal_mode=WAL;")  # lebih toleran untuk multi-worker
        await db.execute(CREATE_BOOKS_TABLE)
        await db.execute(CREATE_TRANSACTIONS_TABLE)
        await db.commit()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- BOOKS (CRUD)
async def list_books(skip: int, limit: int) -> list[dict]:
    async with get_conn() as db:
        cur = await db.execute("SELECT * FROM books ORDER BY id LIMIT ? OFFSET ?", (limit, skip))
        return [dict(r) for r in await cur.fetchall()]


async def get_book(book_id: int) -> Optional[dict]:
    async with get_conn() as db:
        cur = await db.execute("SELECT * FROM books WHERE id = ?", (book_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def insert_book(data: dict) -> int:
    async with get_conn() as db:
        cur = await db.execute(
            "INSERT INTO books (judul, penulis, kategori, tahun_terbit, stok) VALUES (?, ?, ?, ?, ?)",
            (data["judul"], data["penulis"], data["kategori"], data["tahun_terbit"], data["stok"]),
        )
        await db.commit()
        return cur.lastrowid


async def update_book(book_id: int, data: dict) -> bool:
    async with get_conn() as db:
        cur = await db.execute(
            "UPDATE books SET judul=?, penulis=?, kategori=?, tahun_terbit=?, stok=? WHERE id=?",
            (data["judul"], data["penulis"], data["kategori"], data["tahun_terbit"], data["stok"], book_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def delete_book(book_id: int) -> bool:
    """Hard delete: baris dihapus permanen dari database."""
    async with get_conn() as db:
        cur = await db.execute("DELETE FROM books WHERE id = ?", (book_id,))
        await db.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------- STOK
async def get_stok(item_id: int) -> Optional[int]:
    async with get_conn() as db:
        cur = await db.execute("SELECT stok FROM books WHERE id = ?", (item_id,))
        row = await cur.fetchone()
        return row["stok"] if row else None


async def decrement_stok(item_id: int, qty: int) -> None:
    """Kurangi stok tanpa pengecekan (dipakai versi tanpa lock)."""
    async with get_conn() as db:
        await db.execute("UPDATE books SET stok = stok - ? WHERE id = ?", (qty, item_id))
        await db.commit()


async def decrement_stok_atomic(item_id: int, qty: int) -> bool:
    """Kurangi stok hanya jika masih cukup (atomik di level SQL)."""
    async with get_conn() as db:
        cur = await db.execute(
            "UPDATE books SET stok = stok - ? WHERE id = ? AND stok >= ?", (qty, item_id, qty)
        )
        await db.commit()
        return cur.rowcount > 0


async def restore_stok(item_id: int, qty: int) -> None:
    async with get_conn() as db:
        await db.execute("UPDATE books SET stok = stok + ? WHERE id = ?", (qty, item_id))
        await db.commit()


async def potong_stok_tanpa_lock(item_id: int, qty: int) -> bool:
    """VERSI 1 (rawan race condition): read -> jeda -> write tanpa pengaman."""
    stok_terkini = await get_stok(item_id)
    # Jeda buatan: membuka jendela waktu agar request lain ikut membaca stok yang sama
    await asyncio.sleep(0.01)
    if stok_terkini is None or stok_terkini < qty:
        return False
    await decrement_stok(item_id, qty)
    return True


async def potong_stok_dengan_lock(item_id: int, qty: int) -> bool:
    """VERSI 2 (aman): critical section dilindungi asyncio.Lock."""
    # Hanya satu coroutine yang boleh berada di blok ini pada satu waktu.
    # Coroutine lain menunggu (await) di sini tanpa memblokir event loop.
    async with stok_lock:
        stok_terkini = await get_stok(item_id)
        await asyncio.sleep(0.01)
        if stok_terkini is None or stok_terkini < qty:
            return False
        # Pengaman tambahan lintas-worker (lock hanya berlaku per proses)
        return await decrement_stok_atomic(item_id, qty)


# Dipilih saat startup lewat environment variable USE_LOCK
potong_stok = potong_stok_dengan_lock if USE_LOCK else potong_stok_tanpa_lock


# ---------------------------------------------------------------- TRANSACTIONS
async def insert_transaction(item_id: int, qty: int, peminjam: str, status: str = "pending") -> int:
    now = _now()
    async with get_conn() as db:
        cur = await db.execute(
            "INSERT INTO transactions (item_id, qty, peminjam, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (item_id, qty, peminjam, status, now, now),
        )
        await db.commit()
        return cur.lastrowid


async def update_trx_status(trx_id: int, status: str) -> None:
    async with get_conn() as db:
        await db.execute(
            "UPDATE transactions SET status = ?, updated_at = ? WHERE id = ?", (status, _now(), trx_id)
        )
        await db.commit()


async def get_transaction(trx_id: int) -> Optional[dict]:
    async with get_conn() as db:
        cur = await db.execute("SELECT * FROM transactions WHERE id = ?", (trx_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def list_transactions(status: Optional[str], skip: int, limit: int) -> list[dict]:
    query, params = "SELECT * FROM transactions", []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY id LIMIT ? OFFSET ?"
    params += [limit, skip]
    async with get_conn() as db:
        cur = await db.execute(query, params)
        return [dict(r) for r in await cur.fetchall()]
