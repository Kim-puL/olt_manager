import asyncio
from pysnmp.hlapi.v3arch.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget,
    ContextData, ObjectType, ObjectIdentity, walk_cmd
)

class HsgqEponSnmpService:
    def __init__(self, host: str, port: int, community: str):
        self.host = host
        self.port = port
        self.community = community
        self.oids = {
            "name": "1.3.6.1.4.1.50224.3.3.2.1.2",
            "status": "1.3.6.1.4.1.50224.3.3.2.1.8",
            "distance": "1.3.6.1.4.1.50224.3.3.2.1.15",
            "mac_address": "1.3.6.1.4.1.50224.3.3.2.1.7",
            "tx_power": "1.3.6.1.4.1.50224.3.3.3.1.4",
            "rx_power": "1.3.6.1.4.1.50224.3.3.3.1.5",
        }

    async def _walk_oid(self, snmpEngine, key, base_oid, onu_data: dict):
        target = await UdpTransportTarget.create((self.host, self.port),
        timeout=3,    # default 1 → kita buat 3 detik
        retries=2     # default 0 → kita coba 2 kali                                         
        )

        results = walk_cmd(
            snmpEngine,
            CommunityData(self.community, mpModel=1),  # v2c
            target,
            ContextData(),
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False
        )

        async for (errInd, errStat, errIdx, varBinds) in results:
            if errInd or errStat:
                print(f"[{key}] SNMP error: {errInd or errStat}")
                break

            for varBind in varBinds:
                oid_str = str(varBind[0].get_oid())
                suffix = oid_str[len(base_oid) + 1:]
                onu_index = suffix.split('.')[0]

                if onu_index not in onu_data:
                    onu_data[onu_index] = {}

                # Konversi nilai
                if key == "mac_address":
                    raw_bytes = varBind[1].asOctets()
                    value = ":".join(f"{b:02X}" for b in raw_bytes)
                else:
                    value = str(varBind[1])

                onu_data[onu_index][key] = value

    async def get_onus_snmp(self):
        snmpEngine = SnmpEngine()
        onu_data = {}

        # Jalankan semua walk OID secara paralel
        tasks = [
            self._walk_oid(snmpEngine, key, oid, onu_data)
            for key, oid in self.oids.items()
        ]
        await asyncio.gather(*tasks)

        result = []
        for idx, data in onu_data.items():
            try:
                tx = float(data.get("tx_power", 0)) / 100.0
                rx = float(data.get("rx_power", 0)) / 100.0
                result.append({
                    "onu_index": idx,
                    "name": data.get("name", "N/A"),
                    "mac_address": data.get("mac_address", "N/A"),
                    "status": int(data.get("status", -1)),
                    "distance": int(data.get("distance", -1)),
                    "tx_power": f"{tx:.2f}",
                    "rx_power": f"{rx:.2f}"
                })
            except Exception as e:
                print(f"Parse error idx={idx}: {e}")
                continue

        return result


async def main():
    svc = HsgqEponSnmpService("10.1.0.2", 161, "public")
    onus = await svc.get_onus_snmp()
    for onu in onus:
        print(onu)


if __name__ == "__main__":
    asyncio.run(main())
