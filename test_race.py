"""test_race.py - Kirim 2 request transaksi serentak ke buku ber-stok 1.

Jalankan server dulu:
  Tahap 1 (tanpa lock): USE_LOCK=0 uvicorn main:app --port 8000
  Tahap 2 (dengan lock): USE_LOCK=1 uvicorn main:app --port 8000
(Windows PowerShell: $env:USE_LOCK="0"; python -m uvicorn main:app --port 8000)
"""
import threading

import httpx

BASE = "http://127.0.0.1:8000"
ITEM_ID = 1


def reset_stok(client: httpx.Client) -> None:
    """Set stok buku ITEM_ID menjadi 1 lewat endpoint PUT."""
    book = client.get(f"{BASE}/books/{ITEM_ID}").json()
    book.pop("id")
    book["stok"] = 1
    client.put(f"{BASE}/books/{ITEM_ID}", json=book)


def kirim(client: httpx.Client, payload: dict, hasil: list, idx: int, gerbang: threading.Barrier) -> None:
    gerbang.wait()  # kedua thread menunggu, lalu dilepas bersamaan
    hasil[idx] = client.post(f"{BASE}/transactions", json=payload)


def main() -> None:
    payload = {"item_id": ITEM_ID, "qty": 1, "peminjam": "penguji"}
    with httpx.Client(trust_env=False, timeout=30) as client:
        reset_stok(client)

        # Dua request dikirim serentak
        hasil = [None, None]
        gerbang = threading.Barrier(2)
        threads = [
            threading.Thread(target=kirim, args=(client, payload, hasil, i, gerbang))
            for i in range(2)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        res1, res2 = hasil
        print("Respon Request 1:", res1.status_code, res1.json())
        print("Respon Request 2:", res2.status_code, res2.json())

        stok_akhir = client.get(f"{BASE}/books/{ITEM_ID}").json()["stok"]
        print("stok akhir =", stok_akhir)


if __name__ == "__main__":
    main()