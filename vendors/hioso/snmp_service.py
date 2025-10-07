import asyncio
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

class HiosoSnmpService:
    def __init__(self, host: str, port: int, community: str, oids: dict):
        self.host = host
        self.port = port
        self.community = community
        self.oids = oids # OIDs from database
        self.logger = logger

    async def _snmp_walk(self, snmp_engine: SnmpEngine, oid_key: str, oid_value: str) -> dict:
        """Performs an SNMP walk for a single OID using a shared SnmpEngine."""
        results = {}
        try:
            community_data = CommunityData(self.community, mpModel=1)
            transport_target = await UdpTransportTarget.create((self.host, self.port), timeout=10, retries=3)
            
            async for (error_indication, error_status, _, var_binds) in walk_cmd(
                snmp_engine, community_data, transport_target, ContextData(),
                ObjectType(ObjectIdentity(oid_value)), lexicographicMode=False
            ):
                if error_indication or error_status:
                    self.logger.error(f"SNMP Walk Error for {oid_key}: {error_indication or error_status}")
                    break
                for oid_obj, value in var_binds:
                    # Hioso index is the last two parts of the OID
                    parts = str(oid_obj).split('.')
                    if len(parts) > 2:
                        onu_index = ".".join(parts[-2:])
                        results[onu_index] = value.prettyPrint()
        except Exception as e:
            self.logger.error(f"Failed to execute SNMP walk for OID {oid_value}: {e}")
        return results

    async def get_onus_snmp(self) -> list[dict]:
        """Fetches all ONU data using parallel pysnmp walks with a shared SnmpEngine."""
        self.logger.info(f"Starting optimized pysnmp sync for Hioso at {self.host}")
        onus_by_index = {}
        snmp_engine = SnmpEngine()

        try:
            tasks = {key: self._snmp_walk(snmp_engine, key, oid) for key, oid in self.oids.items()}
            all_results = await asyncio.gather(*tasks.values())
            
            snmp_data = dict(zip(tasks.keys(), all_results))
            
            for data_key, values in snmp_data.items():
                for index, value in values.items():
                    if index not in onus_by_index:
                        onus_by_index[index] = {'onu_index': index}
                    onus_by_index[index][data_key] = value

        except Exception as e:
            self.logger.error(f"Failed during parallel pysnmp walks for Hioso: {e}", exc_info=True)
            return []

        self.logger.info(f"Selesai fetch pysnmp untuk Hioso, memproses {len(onus_by_index)} ONU mentah.")
        result = []
        identifier_key = self.oids.get('identifier_key', 'mac_address')

        for index, data in onus_by_index.items():
            if identifier_key not in data:
                self.logger.warning(f"Skipping ONU index {index}: tidak ditemukan identifier '{identifier_key}'. Data: {data}")
                continue
            
            processed_onu = {
                "identifier": data[identifier_key],
                "details": data
            }
            result.append(processed_onu)

        self.logger.info(f"Total ONU Hioso berhasil diproses (pysnmp): {len(result)}")
        return result