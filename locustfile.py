"""locustfile.py - Skenario pengujian beban (Read dan Write).

Skenario Read : GET /books          -> 100 request, konkurensi 20
  locust -f locustfile.py ReadUser  --headless -u 20 -r 20 --host http://127.0.0.1:8000 --csv hasil_read_1w

Skenario Write: POST /transactions  -> 50 request, konkurensi 10
  locust -f locustfile.py WriteUser --headless -u 10 -r 10 --host http://127.0.0.1:8000 --csv hasil_write_1w

Jalankan ulang tiap skenario untuk 1 worker dan 4 worker (ganti nama --csv).
Test berhenti otomatis setelah jumlah request target tercapai.
"""
import random

from locust import HttpUser, constant, events, task

TARGETS = {"GET /books": 100, "POST /transactions": 50}
_counter = {"n": 0}
_env = {}


@events.init.add_listener
def _on_init(environment, **kwargs):
    _env["env"] = environment


@events.request.add_listener
def _on_request(name, **kwargs):
    # Hentikan test setelah target jumlah request tercapai
    if name in TARGETS:
        _counter["n"] += 1
        if _counter["n"] >= TARGETS[name] and _env.get("env") and _env["env"].runner:
            _env["env"].runner.quit()


class ReadUser(HttpUser):
    wait_time = constant(0)

    @task
    def list_books(self):
        self.client.get("/books?skip=0&limit=10", name="GET /books")


class WriteUser(HttpUser):
    wait_time = constant(0)

    @task
    def create_transaction(self):
        self.client.post(
            "/transactions",
            json={"item_id": random.randint(1, 10), "qty": 1, "peminjam": "locust"},
            name="POST /transactions",
        )
