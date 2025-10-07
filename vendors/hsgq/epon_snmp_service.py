import re
from sqlalchemy.orm import Session
import crud
from pysnmp.hlapi.v3arch.asyncio import (
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
    walk_cmd
)
from logger_config import logger

class HsgqEponSnmpService:
    def __init__(self, host: str, port: int, community: str, db: Session):
        self.host = host
        self.port = port
        self.community = community
        self.db = db
        self.logger = logger
        self.OIDS = self._load_oids()

    def _load_oids(self) -> dict:
        """Loads OIDs from the database for hsgq epon."""
        self.logger.info("Memuat OID dari database untuk HSGQ EPON...")
        try:
            oid_records = crud.get_oids_by_vendor_and_model(self.db, vendor_name="hsgq", model="epon")
            if not oid_records:
                self.logger.warning("Tidak ada OID yang ditemukan di database untuk HSGQ EPON. Menggunakan nilai fallback.")
                return self.get_fallback_oids()
            
            oids = {oid.fungsi: oid.oid for oid in oid_records}
            self.logger.info(f"Berhasil memuat {len(oids)} OID dari database.")
            self.logger.debug(f"OID yang dimuat: {oids}")
            return oids
        except Exception as e:
            self.logger.error(f"Gagal memuat OID dari database: {e}", exc_info=True)
            self.logger.warning("Menggunakan nilai OID fallback karena terjadi error.")
            return self.get_fallback_oids()

    def get_fallback_oids(self) -> dict:
        """Returns a hardcoded set of OIDs as a fallback."""
        return {
            'name': '1.3.6.1.4.1.50224.3.3.2.1.2',
            'tx_power': '1.3.6.1.4.1.50224.3.3.3.1.4',
            'rx_power': '1.3.6.1.4.1.50224.3.3.3.1.5',
            'status': '1.3.6.1.4.1.50224.3.3.2.1.8',
            'distance': '1.3.6.1.4.1.50224.3.3.2.1.15',
            'mac_address': '1.3.6.1.4.1.50224.3.3.2.1.7',
        }

    async def _snmp_walk(self, snmp_engine: SnmpEngine, oid_key: str, oid_value: str) -> dict:
        """Performs an SNMP walk for a single OID using a shared SnmpEngine."""
        results = {}
        self.logger.debug(f"Memulai SNMP walk untuk {oid_key} di {self.host}")
        try:
            community_data = CommunityData(self.community, mpModel=1)
            transport_target = await UdpTransportTarget.create((self.host, self.port), timeout=10, retries=3)
            
            async for (error_indication, error_status, _, var_binds) in walk_cmd(
                snmp_engine, community_data, transport_target, ContextData(),
                ObjectType(ObjectIdentity(oid_value)), lexicographicMode=False
            ):
                if error_indication or error_status:
                    self.logger.error(f"SNMP Walk Error untuk {oid_key}: {error_indication or error_status}")
                    break
                for oid_obj, value in var_binds:
                    oid_str = str(oid_obj)
                    self.logger.debug(f"Menerima OID: {oid_str}, Value: {value.prettyPrint()}")
                    match = re.search(r'\.(\d+)$|(\d+)\.(?:0\.0|65535\.65535)$', oid_str)
                    if match:
                        onu_index = match.group(1) or match.group(2)
                        results[onu_index] = value.prettyPrint()
                        self.logger.debug(f"Menemukan index ONU: {onu_index} untuk {oid_key} dengan nilai: {value.prettyPrint()}")
                    else:
                        self.logger.warning(f"Tidak dapat mengekstrak index ONU dari OID: {oid_str} untuk {oid_key}")
        except Exception as e:
            self.logger.error(f"Gagal mengeksekusi SNMP walk untuk OID {oid_value}: {e}", exc_info=True)
        
        self.logger.debug(f"Menyelesaikan SNMP walk untuk {oid_key}, menemukan {len(results)} item.")
        return results

    async def get_onus(self) -> dict:
        """Fetches all ONU data using sequential pysnmp walks."""
        self.logger.info(f"Memulai walk SNMP sekuensial untuk HSGQ EPON di {self.host}")
        onus_by_index = {}
        snmp_engine = SnmpEngine()
        snmp_data = {}

        try:
            # Iterating over OIDs sequentially instead of in parallel
            for key, oid in self.OIDS.items():
                self.logger.debug(f"Fetching OID: {key} ({oid})")
                results = await self._snmp_walk(snmp_engine, key, oid)
                snmp_data[key] = results
                self.logger.debug(f"Menerima {len(results)} hasil untuk {key}")

            self.logger.debug(f"Data SNMP mentah yang terkumpul: {snmp_data}")

            for data_key, values in snmp_data.items():
                for index, value in values.items():
                    if index not in onus_by_index:
                        onus_by_index[index] = {'onu_index': index}
                    onus_by_index[index][data_key] = value
            
            self.logger.debug(f"Data ONU yang diindeks sebelum diproses: {onus_by_index}")

        except Exception as e:
            self.logger.error(f"Gagal saat walk SNMP sekuensial untuk HSGQ EPON: {e}", exc_info=True)
            return {"error": str(e)}

        final_onus = []
        status_map = {'1': 'Online', '2': 'Offline'}

        self.logger.info(f"Memproses {len(onus_by_index)} ONU yang ditemukan...")
        for index, data in onus_by_index.items():
            self.logger.debug(f"Memproses ONU dengan index: {index}, data: {data}")
            raw_mac = data.get('mac_address')
            if not raw_mac:
                self.logger.warning(f"Melewatkan ONU index {index}: Alamat MAC kosong.")
                continue

            cleaned_mac = raw_mac.replace('0x', '').replace(' ', '').replace(':', '').lower()
            
            if len(cleaned_mac) == 12:
                formatted_mac = ':'.join(cleaned_mac[i:i+2] for i in range(0, len(cleaned_mac), 2))
            else:
                self.logger.warning(f"Melewatkan ONU index {index}: Panjang alamat MAC tidak valid setelah dibersihkan: {cleaned_mac}")
                continue

            try:
                tx_power = f"{float(data.get('tx_power', 0)) / 100.0:.2f} dBm"
                rx_power = f"{float(data.get('rx_power', 0)) / 100.0:.2f} dBm"
            except (ValueError, TypeError):
                tx_power = rx_power = "N/A"
                self.logger.warning(f"Tidak dapat mem-parsing power level untuk ONU index {index}. Data: tx={data.get('tx_power')}, rx={data.get('rx_power')}")


            details = {
                'onu_index': index,
                'name': data.get('name', 'N/A'),
                'mac_address': formatted_mac,
                'tx_power': tx_power,
                'rx_power': rx_power,
                'status': status_map.get(data.get('status'), 'Unknown'),
                'distance': f"{data.get('distance', 'N/A')} m",
            }
            self.logger.debug(f"Detail ONU yang telah diproses untuk index {index}: {details}")

            final_onus.append({
                'identifier': formatted_mac,
                'pon_interface': 'N/A',
                'vendor_name': 'hsgq_epon',
                'details': details
            })

        self.logger.info(f"Berhasil memproses {len(final_onus)} ONU dari HSGQ EPON.")
        return {"count": len(final_onus), "onus": final_onus}
