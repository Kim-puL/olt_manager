import asyncio
import logging
from vendors.hioso.telnet_service import HiosoTelnetService

# --- KONFIGURASI ---
# Ganti dengan detail koneksi OLT Hioso Anda
HOST = "10.1.0.10"
PORT = 23
USER = "root"
PASSWORD = "admin"

# Konfigurasi logging untuk menampilkan output debug
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

async def main():
    """
    Fungsi utama untuk menjalankan tes debug pada HiosoTelnetService.
    """
    logging.info(f"Memulai tes debug untuk Hioso OLT di {HOST}...")
    
    # 1. Inisialisasi service
    # Menggunakan implementasi yang sudah diperbaiki (jika Anda menyetujui perubahan sebelumnya)
    service = HiosoTelnetService(
        host=HOST,
        port=PORT,
        username=USER,
        password=PASSWORD
    )
    
    # 2. Panggil metode get_onus() untuk mengambil data ONU
    logging.info("Memanggil service.get_onus()...")
    result = await service.get_onus()
    logging.info("Panggilan service.get_onus() selesai.")
    
    # 3. Cetak hasil yang diterima
    print("\n" + "="*80)
    print("HASIL DARI get_onus()")
    print("="*80)

    if "error" in result:
        print(f"Terjadi error: {result['error']}")
    else:
        print(f"Berhasil mendapatkan data: {result.get('count', 0)} ONU ditemukan.")
        
        # Cetak daftar ONU yang di-parse
        if result.get("onus"):
            print("\n--- DAFTAR ONU ---")
            for i, onu in enumerate(result["onus"]):
                print(f"{i+1}. Identifier: {onu.get('identifier')}, Interface: {onu.get('pon_interface')}")
            print("------------------")

    # 4. Cetak log debug lengkap dari service
    # Ini adalah bagian paling penting untuk debugging
    print("\n" + "="*80)
    print("LOG DEBUG LENGKAP DARI SERVICE")
    print("="*80)
    if result.get("debug_log"):
        for log_entry in result["debug_log"]:
            # Cetak log mentah untuk melihat semua karakter
            print(repr(log_entry))
    else:
        print("Tidak ada log debug yang dihasilkan.")
        
    print("="*80)
    logging.info("Tes debug selesai.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Tes dihentikan oleh pengguna.")
