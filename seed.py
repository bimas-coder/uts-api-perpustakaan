"""seed.py - Reset database dan isi 10 data buku awal.

Jalankan: python seed.py   (hentikan server dulu bila ingin reset penuh)
"""
import asyncio

import aiosqlite

import database as db

BOOKS = [
    ("Laskar Pelangi", "Andrea Hirata", "Novel", 2005, 100),
    ("Bumi Manusia", "Pramoedya Ananta Toer", "Novel", 1980, 100),
    ("Filosofi Teras", "Henry Manampiring", "Filsafat", 2018, 100),
    ("Atomic Habits", "James Clear", "Pengembangan Diri", 2018, 100),
    ("Clean Code", "Robert C. Martin", "Pemrograman", 2008, 100),
    ("Fluent Python", "Luciano Ramalho", "Pemrograman", 2015, 100),
    ("Sapiens", "Yuval Noah Harari", "Sejarah", 2011, 100),
    ("Dilan 1990", "Pidi Baiq", "Novel", 2014, 100),
    ("Algoritma dan Struktur Data", "Rinaldi Munir", "Informatika", 2016, 100),
    ("Sistem Operasi Modern", "Andrew S. Tanenbaum", "Informatika", 2014, 100),
]


async def main():
    await db.init_db()
    async with aiosqlite.connect(db.DB_PATH, timeout=30) as conn:
        await conn.execute("DELETE FROM transactions")
        await conn.execute("DELETE FROM books")
        await conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('books', 'transactions')")
        await conn.executemany(
            "INSERT INTO books (judul, penulis, kategori, tahun_terbit, stok) VALUES (?, ?, ?, ?, ?)", BOOKS
        )
        await conn.commit()
    print(f"Seed selesai: {len(BOOKS)} buku dimasukkan.")


if __name__ == "__main__":
    asyncio.run(main())
