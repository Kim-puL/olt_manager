import asyncio
import asyncssh
import re
from typing import List, Dict, Any
from logger_config import logger

class HsgqSshService:
    def __init__(self, host, port, username, password):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.logger = logger

    async def get_onus(self) -> Dict[str, Any]:
        self.logger.info(f"Connecting to {self.host}:{self.port}...")
        output = ""
        try:
            async with asyncssh.connect(
                self.host, port=self.port, username=self.username,
                password=self.password, known_hosts=None,
                # Algoritma lawas untuk kompatibilitas OLT HSGQ
                kex_algs=["diffie-hellman-group1-sha1", "diffie-hellman-group14-sha1"],
                encryption_algs=["aes128-cbc", "3des-cbc"],
                mac_algs=["hmac-sha1"],
                server_host_key_algs=["ssh-rsa", "ssh-dss"],
            ) as conn:
                self.logger.info("Connection successful.")
                
                proc = await conn.create_process(term_type="vt100")
                self.logger.debug("Interactive process created.")

                async def send(cmd, delay=1):
                    self.logger.debug(f"Sending command: {cmd}")
                    proc.stdin.write(cmd + "\n")
                    await asyncio.sleep(delay)

                # === Jalankan command step-by-step ===
                await send("enable", 1)

                try:
                    # Cek apakah muncul prompt password
                    password_prompt = await asyncio.wait_for(proc.stdout.read(1024), timeout=0.5)
                    if 'Password:' in password_prompt:
                        self.logger.debug("Enable password prompt detected, sending password...")
                        await send(self.password, 1)
                except asyncio.TimeoutError:
                    pass  # Tidak ada prompt password

                await send("configure", 1)
                await send("show ont-optical all", 10)

                # === Baca output sampai prompt balik atau timeout ===
                while True:
                    try:
                        data = await asyncio.wait_for(proc.stdout.read(9999), timeout=2.0)
                        if not data:
                            break
                        
                        output += data
                        self.logger.debug(f"Read chunk:\n{data}")

                        if "(config)#" in data:
                            self.logger.debug("Found exit prompt, stopping read loop.")
                            break
                    except asyncio.TimeoutError:
                        self.logger.debug("Timeout waiting for more output, assuming command finished.")
                        break

        except Exception as e:
            self.logger.error(f"FATAL_ERROR: {e}")
            return {
                "error": f"An exception of type {type(e).__name__} occurred: {e}",
            }

        # === Parsing hasil output ===
        onus = self._parse_onus(output)
        return {"count": len(onus), "onus": onus}

    def _parse_onus(self, raw_output: str) -> List[Dict[str, Any]]:
        self.logger.debug("Parsing output with multiline regex...")
        parsed_onus = []

        # Bersihkan CR ganda
        text = raw_output.replace("\r", "")

        # Regex multiline: cari semua baris dengan pola PON/ONU → ONT-NAME
        pattern = re.compile(
            r"(\d+/\d+)\s+"          # PON/ONU
            r"(\S+)\s+"              # ONT-SN
            r"(\d+)\s+C\s+"          # Temp
            r"([\d.]+)\s+V\s+"       # Voltage
            r"([\d.]+)\s+mA\s+"      # Bias
            r"([\d.\-]+)\s+dBm\s+"   # Tx power
            r"([\d.\-]+)\s+dBm\s+"   # Rx power
            r"([A-Za-z0-9_\-/]+)",   # ONT-Name (huruf, angka, underscore, slash, strip)
            re.MULTILINE
        )

        matches = pattern.findall(text)
        for m in matches:
            onu = {
                "pon_onu": m[0],
                "ont_sn": m[1],
                "temp": m[2] + " C",
                "voltage": m[3] + " V",
                "bias": m[4] + " mA",
                "tx_power": m[5] + " dBm",
                "rx_power": m[6] + " dBm",
                "ont_name": m[7],
            }
            parsed_onus.append(onu)

        self.logger.debug(f"Parsed {len(parsed_onus)} ONUs.")
        
        # Normalisasi data
        normalized_onus = []
        for onu_data in parsed_onus:
            normalized_onus.append({
                "identifier": onu_data["ont_sn"],
                "pon_interface": onu_data["pon_onu"],
                "vendor_name": "hsgq",
                "details": onu_data
            })
            
        return normalized_onus
