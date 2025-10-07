# OLT Manager SaaS API

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Framework](https://img.shields.io/badge/Framework-FastAPI-green.svg)](https://fastapi.tiangolo.com/)
[![Database](https://img.shields.io/badge/Database-SQLAlchemy%20%7C%20SQLite-orange.svg)](https://www.sqlalchemy.org/)

API SaaS multi-tenant untuk mengelola dan memantau Optical Line Terminals (OLT) dan Optical Network Units (ONU) terkait dari berbagai vendor.

## Fitur

*   **Arsitektur Multi-tenant:** Mengelola banyak tenant dengan data yang terisolasi secara aman.
*   **Otentikasi Berbasis JWT:** Amankan API Anda dengan JSON Web Tokens.
*   **Manajemen Spesifik per Vendor:** Mudah diperluas untuk mendukung berbagai vendor OLT (saat ini mendukung Hioso, HSGQ, ZTE).
*   **Komunikasi Asinkron:** Komunikasi non-blocking dengan OLT menggunakan Telnet, SSH, dan SNMP.
*   **Tugas Latar Belakang:** Tugas yang berjalan lama seperti sinkronisasi ONU ditangani di latar belakang menggunakan Celery.
*   **Manajemen Langganan:** Paket langganan dan manajemen kuota bawaan.
*   **Operasi CRUD:** Operasi CRUD yang komprehensif untuk Tenant, User, OLT, ONU, dan OID.
*   **Dokumentasi API Otomatis:** Dokumentasi API interaktif yang didukung oleh Swagger UI dan ReDoc.

## Teknologi yang Digunakan

*   **Backend:** [Python](https://www.python.org/) dengan [FastAPI](https://fastapi.tiangolo.com/)
*   **Database:** [SQLAlchemy](https://www.sqlalchemy.org/) dengan [SQLite](https://www.sqlite.org/index.html)
*   **Migrasi Database:** [Alembic](https://alembic.sqlalchemy.org/en/latest/)
*   **Otentikasi:** [python-jose](https://github.com/mpdavis/python-jose) untuk JWT
*   **Tugas Latar Belakang:** [Celery](https://docs.celeryq.dev/en/stable/)
*   **Linting:** [Ruff](https://beta.ruff.rs/docs/)

## Arsitektur

Aplikasi ini dibangun dengan desain modular berbasis vendor. Setiap vendor OLT memiliki modul khusus di direktori `vendors`, yang berisi implementasi spesifik untuk komunikasi Telnet, SSH, dan SNMP. Aplikasi ini sangat bergantung pada `asyncio` untuk komunikasi non-blocking dengan OLT.

## Instalasi

1.  **Clone repositori:**
    ```bash
    git clone https://github.com/username-anda/olt-manager.git
    cd olt-manager
    ```

2.  **Instal dependensi:**
    ```bash
    pip install -r requirements.txt
    ```

## Menjalankan Aplikasi

Untuk menjalankan aplikasi secara lokal, gunakan `uvicorn`:

```bash
uvicorn main:app --reload
```

API akan tersedia di `http://127.0.0.1:8000`.

## Dokumentasi API

Setelah aplikasi berjalan, Anda dapat mengakses dokumentasi API interaktif di:

*   **Swagger UI:** `http://127.0.0.1:8000/docs`
*   **ReDoc:** `http://127.0.0.1:8000/redoc`

## Database

Aplikasi ini menggunakan database SQLite. File `olt_manager.db` dibuat secara otomatis saat aplikasi dimulai.

### Migrasi Database

Proyek ini menggunakan Alembic untuk mengelola migrasi skema database.

Untuk membuat migrasi baru setelah mengubah model di `database/models.py`:

```bash
alembic revision --autogenerate -m "Pesan migrasi Anda"
```

Untuk menerapkan migrasi ke database:

```bash
alembic upgrade head
```

## Konvensi Pengembangan

*   **Logika Spesifik Vendor:** Semua kode spesifik vendor harus ditempatkan di modulnya sendiri di dalam direktori `vendors`.
*   **Operasi Asinkron:** Gunakan `async` dan `await` untuk semua operasi I/O-bound, terutama saat berkomunikasi dengan OLT.
*   **Konfigurasi:** Konfigurasi spesifik lingkungan dikelola melalui file `.env`. File `.env.example` harus disediakan untuk mendaftar semua variabel lingkungan yang diperlukan.

## Deployment

Direktori `deployment_configs` berisi contoh file layanan untuk mendeploy aplikasi menggunakan:

*   **Gunicorn:** Sebagai server aplikasi.
*   **Celery:** Untuk menjalankan background worker dan beat scheduler.
*   **Nginx:** Sebagai reverse proxy.

Silakan merujuk ke `README.md` di dalam direktori `deployment_configs` untuk detail lebih lanjut.
