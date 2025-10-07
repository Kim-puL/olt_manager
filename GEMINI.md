# OLT Manager SaaS API

## Project Overview

This project is a multi-tenant SaaS API for managing and monitoring Optical Line Terminals (OLTs) and their associated Optical Network Units (ONUs) from various vendors.

*   **Purpose:** To provide a centralized platform for managing OLTs from different manufacturers.
*   **Main Technologies:**
    *   **Backend:** Python with FastAPI
    *   **Database:** SQLAlchemy with SQLite
    *   **Authentication:** JWT-based authentication
*   **Architecture:**
    *   Multi-tenant SaaS architecture.
    *   Modular, vendor-based design with specific implementations for each vendor (Hioso, HSGQ, ZTE).
    *   Asynchronous communication with OLTs using Telnet, SSH, and SNMP.

## Building and Running

### 1. Install Dependencies

To install the required Python packages, run the following command:

```bash
pip install -r requirements.txt
```

### 2. Run the Application

This is a FastAPI application that can be run using `uvicorn`.

```bash
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

### 3. Database

The application uses a SQLite database, and the `olt_manager.db` file is created automatically when the application starts.

Mulai sekarang, setiap kali Anda ingin mengubah struktur database (misalnya menambah kolom baru di models.py), alur kerjanya adalah:

  1.  Ubah Model Anda: Lakukan perubahan yang Anda inginkan pada file database/models.py.
  2.  Buat Revisi Baru: Jalankan perintah berikut di terminal:

  `bash
      alembic revision --autogenerate -m "Deskripsi perubahan Anda"
      `
      Contoh: alembic revision --autogenerate -m "Add last_login to User model"
  3.  Terapkan Revisi: Jalankan perintah berikut untuk menerapkan perubahan tersebut ke database:

  `bash
      alembic upgrade head
      `


  Dengan cara ini, semua perubahan pada skema database Anda akan tercatat, aman, dan terkendali.

## Development Conventions

*   **Vendor-Specific Logic:** Each OLT vendor has a dedicated module in the `vendors` directory. This is where the specific implementations for Telnet, SSH, and SNMP communication for each vendor are located.
*   **Asynchronous Operations:** The application heavily relies on `asyncio` for non-blocking communication with OLTs.
*   **Database:** The database schema is defined in `database/models.py` and the application creates the database from these models. There is no database migration tool like Alembic configured.
*   **Testing:** There are no automated tests in the project.
