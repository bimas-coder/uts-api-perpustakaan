https://youtu.be/gWsLTRFdxy8

# API Perpustakaan - UTS Komputasi Paralel dan Terdistribusi

Nama: Bima Adinda Putra | NIM: 221220065 | Kelas: 31

REST API peminjaman buku: FastAPI + SQLite (aiosqlite), transaksi asinkron (BackgroundTasks), pengaman race condition (asyncio.Lock).

## Instalasi
```bash
python -m venv venv
source venv/bin/activate          # Linux / Mac
venv\Scripts\Activate.ps1         # Windows PowerShell
pip install -r requirements.txt
python seed.py                  # isi 10 data buku
```

## Menjalankan
```bash
uvicorn main:app --port 8000                 # 1 worker
uvicorn main:app --workers 4 --port 8000     # 4 worker
```
Swagger UI: http://127.0.0.1:8000/docs

## Endpoint
| Method | Path | Keterangan |
|---|---|---|
| GET | /books?skip=0&limit=10 | Daftar buku |
| GET | /books/{id} | Detail buku |
| POST | /books | Tambah buku (201) |
| PUT | /books/{id} | Perbarui buku (200) |
| DELETE | /books/{id} | Hapus permanen (200) |
| POST | /transactions | Buat transaksi, balas `pending` (202) |
| GET | /transactions?status=pending | Daftar transaksi |
| GET | /transactions/{id} | Detail + status terkini |

Status transaksi: `pending -> processing -> completed / failed`.
Stok habis -> `409 Conflict`. Buku tidak ada -> `404`. Validasi gagal -> `422`.

## Uji race condition
```bash
python seed.py
USE_LOCK=0 uvicorn main:app --port 8000   # Tahap 1: tanpa lock (stok jadi -1)
python test_race.py
# hentikan server, lalu:
USE_LOCK=1 uvicorn main:app --port 8000   # Tahap 2: dengan lock (1 sukses, 1x 409)
python test_race.py
```
Windows PowerShell: `$env:USE_LOCK="0"; uvicorn main:app --port 8000`

## Uji beban (Locust)
```bash
python seed.py
locust -f locustfile.py ReadUser  --headless -u 20 -r 20 --host http://127.0.0.1:8000 --csv read_1w
locust -f locustfile.py WriteUser --headless -u 10 -r 10 --host http://127.0.0.1:8000 --csv write_1w
```
Ulangi dengan server `--workers 4` (ganti nama `--csv`).

## Referensi
- FastAPI, asyncio, aiosqlite, Uvicorn, Locust (dokumentasi resmi)
