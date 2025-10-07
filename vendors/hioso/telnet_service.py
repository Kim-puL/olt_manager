import asyncio
import telnetlib3
import re
from typing import List, Dict, Any
from logger_config import logger

class HiosoTelnetService:
    def __init__(self, host, port, username, password):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.access_password = password
        self.enable_password = password
        self.reader = None
        self.writer = None
        self.logger = logger

    async def _read_until(self, prompt: str, timeout: int = 15) -> str:
        try:
            output_str = await asyncio.wait_for(
                self.reader.readuntil(prompt.encode('ascii')),
                timeout=timeout
            )
            self.logger.debug(f"RECV: {repr(output_str)}")
            return output_str
        except asyncio.TimeoutError:
            err_msg = f"Timeout waiting for prompt: {prompt}"
            self.logger.error(err_msg)
            raise asyncio.TimeoutError(err_msg)

    async def _write(self, data: str):
        self.logger.debug(f"SENT: {repr(data)}")
        self.writer.write(data)
        await self.writer.drain()

    async def connect(self):
        self.logger.info(f"Connecting to {self.host}:{self.port}...")
        # Atur encoding di sini, maka semua operasi read/write akan menggunakan string
        self.reader, self.writer = await telnetlib3.open_connection(
            self.host, self.port, encoding='ascii', encoding_errors='ignore'
        )
        
        # Perbaikan: Tunggu prompt 'login:' (tanpa 'EPON') berdasarkan output debug
        await self._read_until("login:")
        await self._write(self.username + "\n")
        
        await self._read_until("Password:")
        await self._write(self.password + "\n")

        await self._read_until("Revision:")
        await self._write("\n")

        await self._read_until("Access Password:")
        await self._write(self.access_password + "\n")

        await self._read_until("EPON>")
        await self._write("enable\n")

        await self._read_until("Enable Password:")
        await self._write(self.enable_password + "\n")

        await self._read_until("EPON#")
        self.logger.info("Connection successful and in enable mode.")

    async def disconnect(self):
        if self.writer and not self.writer.is_closing():
            self.logger.info("Disconnecting...")
            await self._write("exit\n")
            self.writer.close()

    def _parse_onus(self, raw_output: str) -> List[Dict[str, Any]]:
        self.logger.debug(f"--- STARTING PARSE of {len(raw_output)} bytes ---")
        
        # Bersihkan marker paging dan karakter kontrol
        cleaned_output = re.sub(r'--+ Press Enter Or Space To Continue --+[]*', '\n', raw_output)
        lines = cleaned_output.splitlines()

        parsed_onus = []
        onu_pattern = re.compile(
            r"\s*(\d+/\d+:\d+)\s+"      # onuId (e.g., 1/1:13)
            r"([0-9a-fA-F:.-]+)\s+"   # onuMac (e.g., 98c7a4.5e30b8)
            r"(\w+)\s+"             # status (e.g., Up)
            r"(\d+)\s+"             # ports
            r"(\w+)\s+"             # chipId (e.g., 0x0)
            r"(\w+)\s+"             # version (e.g., 0x4853)
            r"(\d+)\s+"             # flags
            r"(\w+)\s+"             # authMode (e.g., Undef)
            r"(\d+)\s+"             # distance
            r"(.+)"                   # time (e.g., 22 hours 2 minites 15 seconds)
        )

        for i, line in enumerate(lines):
            # Hapus karakter kontrol (ASCII 0-31 dan 127)
            line = re.sub(r'[\x00-\x1F\x7F]', '', line).strip()
            if not line:
                continue

            match = onu_pattern.match(line)
            if match:
                details = {
                    "onuId": match.group(1),
                    "onuMac": match.group(2),
                    "status": match.group(3),
                    "ports": int(match.group(4)),
                    "chipId": match.group(5),
                    "version": match.group(6),
                    "flags": int(match.group(7)),
                    "authMode": match.group(8),
                    "distance": int(match.group(9)),
                    "time": match.group(10).strip()
                }
                
                # Data utama yang akan dinormalisasi
                onu_data = {
                    "identifier": re.sub(r'[^0-9a-fA-F]', '', details["onuMac"]),
                    "pon_interface": details["onuId"],
                    "vendor_name": "hioso",
                    "details": details
                }
                parsed_onus.append(onu_data)
                self.logger.debug(f"  [Line {i+1}] MATCHED: {details}")
            else:
                self.logger.debug(f"  [Line {i+1}] NO MATCH: '{line}'")
        
        self.logger.debug(f"--- FINISHED PARSE: Found {len(parsed_onus)} ONUs ---")

        return parsed_onus


    async def get_onus(self) -> Dict[str, Any]:
        try:
            await self.connect()

            await self._write("configure terminal\n")
            await self._read_until("EPON(config)#")
            
            await self._write("epon\n")
            await self._read_until("EPON(epon)#")

            all_parsed_onus = []
            # Loop ini akan mencoba semua port yang ada di dalam range.
            for i in range(1, 3): # Coba port 1/1 dan 1/2
                pon_interface = f"pon 1/{i}"
                self.logger.info(f"--- Checking {pon_interface} ---")
                await self._write(f"{pon_interface}\n")
                
                prompt = f"EPON(epon-pon-1/{i})#"
                try:
                    await self._read_until(prompt)
                except asyncio.TimeoutError:
                    self.logger.warning(f"Timeout waiting for {prompt}. Assuming port does not exist. Skipping.")
                    await self._write("exit\n")
                    try:
                        await asyncio.wait_for(self._read_until("EPON(epon)#"), timeout=2.0)
                    except asyncio.TimeoutError:
                        self.logger.error("Could not return to epon mode. Aborting.")
                        raise
                    continue

                await self._write("show onu all\n")
                await asyncio.sleep(0.5) # Give the device a moment to process

                full_output = ""
                while True:
                    try:
                        chunk = await asyncio.wait_for(self.reader.read(4096), timeout=5.0) # Increased timeout
                        if not chunk:
                            break
                        
                        full_output += chunk
                        self.logger.debug(f"RECV_CHUNK: {repr(chunk)}")

                        if "---- More ----" in chunk or "Press Enter Or Space To Continue" in chunk:
                            full_output = re.sub(r'--+ (More|Press Enter Or Space To Continue) --+', '', full_output)
                            self.logger.debug("Paging detected, sending space.")
                            await self._write(" ")
                            await asyncio.sleep(0.2)

                        if prompt in full_output:
                            self.logger.debug("Final prompt found in output.")
                            break

                    except asyncio.TimeoutError:
                        self.logger.debug("Read timeout, assuming end of command output.")
                        break
                
                self.logger.debug(f"--- RAW OUTPUT BEFORE PARSE ---\n{full_output}\n---------------------------------")
                parsed_onus_port = self._parse_onus(full_output)
                all_parsed_onus.extend(parsed_onus_port)

                # Karena koneksi tidak putus, kita bisa keluar ke menu parent
                await self._write("exit\n")
                await self._read_until("EPON(epon)#")

            return {"count": len(all_parsed_onus), "onus": all_parsed_onus}

        except Exception as e:
            self.logger.error(f"FATAL_ERROR: {e}")
            return {"error": f"An exception of type {type(e).__name__} occurred: {e}"}
        finally:
            await self.disconnect()