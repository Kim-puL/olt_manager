import os
import sys
import asyncio
from pprint import pprint

# Menambahkan direktori root proyek ke path Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vendors.hsgq.snmp_service import HsgqSnmpService

# --- KONFIGURASI ---
OLT_IP = "10.1.0.11"  # Ganti dengan IP OLT HSGQ Anda
OLT_SNMP_PORT = 161
OLT_COMMUNITY = "public"  # Ganti dengan community string Anda

async def run_hsgq_snmp_test():
    """
    Menjalankan tes asinkron untuk HsgqSnmpService.
    """
    print(f"Memulai tes SNMP untuk HSGQ OLT di {OLT_IP}...")

    service = HsgqSnmpService(
        host=OLT_IP,
        port=OLT_SNMP_PORT,
        community=OLT_COMMUNITY
    )

    print("Memanggil service.get_onus_snmp()...")
    onus = await service.get_onus_snmp()

    print("\nPanggilan service.get_onus_snmp() selesai.")
    print("\n" + "="*80)
    print("HASIL DARI get_onus_snmp()")
    print("="*80)

    if not onus:
        print("Tidak ada ONU yang ditemukan atau terjadi error.")
        return

    print(f"Berhasil mendapatkan data: {len(onus)} ONU ditemukan.")
    
    print("\n--- DAFTAR ONU ---")
    for i, onu_data in enumerate(onus, 1):
        print(f"{i}. Identifier (SN): {onu_data.get('identifier')}")
        pprint(onu_data)
        print("-" * 18)

if __name__ == "__main__":
    asyncio.run(run_hsgq_snmp_test())