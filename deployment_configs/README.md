# Panduan Deployment OLT Manager di VPS

Ini adalah panduan untuk mendeploy aplikasi OLT Manager API menggunakan Gunicorn, Systemd, dan Nginx di server Linux (misalnya Ubuntu).

## Prasyarat

1.  Server VPS baru (misalnya Ubuntu 22.04).
2.  Domain yang sudah diarahkan ke IP VPS Anda (opsional, untuk HTTPS).
3.  Akses root atau user dengan hak sudo.
4.  Database server seperti PostgreSQL sudah terinstall.
5.  Message broker seperti Redis sudah terinstall (`sudo apt install redis-server`).

## Langkah-langkah Deployment

### 1. Persiapan Awal di VPS

-   Update sistem: `sudo apt update && sudo apt upgrade`
-   Install Python, pip, dan Nginx: `sudo apt install python3-pip python3-venv nginx`
-   Buat database dan user di PostgreSQL untuk aplikasi Anda.

### 2. Upload dan Setup Proyek

-   Upload kode proyek Anda ke direktori di VPS, misalnya `/home/user/olt_manager`.
-   Masuk ke direktori proyek: `cd /home/user/olt_manager`
-   Buat dan aktifkan virtual environment: 
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
-   Install dependencies: `pip install -r requirements.txt` dan `pip install gunicorn psycopg2-binary`.

### 3. Konfigurasi Environment (`.env`)

-   Buat file `.env` di direktori proyek: `nano .env`
-   Isi file tersebut dengan konfigurasi produksi. Ganti nilai-nilai placeholder.

    ```ini
    # Ganti dengan kunci rahasia yang kuat
    SECRET_KEY=your_strong_production_secret_key

    # URL Database PostgreSQL Anda
    DATABASE_URL=postgresql://db_user:db_password@localhost:5432/db_name

    # URL Redis (jika di-host yang sama)
    CELERY_BROKER_URL=redis://localhost:6379/0
    CELERY_RESULT_BACKEND=redis://localhost:6379/0

    # Konfigurasi Stripe (jika digunakan)
    STRIPE_SECRET_KEY=sk_live_your_stripe_key
    STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
    ```

### 4. Konfigurasi Systemd Services

-   Salin file-file service ke direktori systemd di VPS:
    ```bash
    sudo cp deployment_configs/gunicorn.service /etc/systemd/system/
    sudo cp deployment_configs/celery_worker.service /etc/systemd/system/
    sudo cp deployment_configs/celery_beat.service /etc/systemd/system/
    ```
-   **PENTING:** Edit setiap file `.service` yang baru disalin. Ganti `user` dan `/path/to/your/project` sesuai dengan setup Anda.
    ```bash
    sudo nano /etc/systemd/system/gunicorn.service
    # Ulangi untuk file lainnya
    ```
-   Reload daemon systemd, lalu start dan enable services:
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl start gunicorn.service
    sudo systemctl enable gunicorn.service
    
    sudo systemctl start celery_worker.service
    sudo systemctl enable celery_worker.service

    sudo systemctl start celery_beat.service
    sudo systemctl enable celery_beat.service
    ```
-   Cek status untuk memastikan semuanya berjalan: `sudo systemctl status gunicorn.service`

### 5. Konfigurasi Nginx

-   Buat file konfigurasi Nginx baru:
    ```bash
    sudo nano /etc/nginx/sites-available/olt_manager
    ```
-   Salin konten dari file `deployment_configs/nginx_config` ke dalamnya. Ganti `your_domain.com` dengan domain atau IP VPS Anda.
-   Buat symbolic link untuk mengaktifkan site:
    ```bash
    sudo ln -s /etc/nginx/sites-available/olt_manager /etc/nginx/sites-enabled/
    ```
-   Test konfigurasi Nginx dan restart:
    ```bash
    sudo nginx -t
    sudo systemctl restart nginx
    ```

### 6. (Opsional) Setup HTTPS dengan Certbot

-   Install Certbot: `sudo apt install certbot python3-certbot-nginx`
-   Dapatkan sertifikat SSL: `sudo certbot --nginx -d your_domain.com`


Selesai! Aplikasi Anda sekarang seharusnya sudah berjalan di domain Anda.
