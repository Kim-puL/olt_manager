import asyncio
import asyncssh
import re
from typing import List, Dict, Any
from logger_config import logger


class HsgqEponSshService:
    def __init__(self, host, port, username, password, delay=20, timeout=30):
        self.host = host
        self.port = port
        # Username/password dipakai untuk SSH & CLI (login 2x)
        self.ssh_user = username
        self.ssh_pass = password
        self.cli_user = username
        self.cli_pass = password
        self.delay = delay
        self.timeout = timeout
        self.logger = logger

    async def wait_for_prompt(self, proc, prompts, timeout=20):
        """Menunggu hingga salah satu prompt muncul.
        Tangani --More-- agar output tidak terpotong.
        """
        if isinstance(prompts, str):
            prompts = [prompts]

        buf = ""
        start = asyncio.get_event_loop().time()
        while True:
            if asyncio.get_event_loop().time() - start > timeout:
                self.logger.warning(f"Timeout waiting for prompts: {prompts}")
                self.logger.debug(f"Read buffer after timeout:\n{buf.strip()}")
                return buf

            try:
                ch = await asyncio.wait_for(proc.stdout.read(1), timeout=1)
            except asyncio.TimeoutError:
                continue

            if not ch:
                continue

            if isinstance(ch, bytes):
                ch = ch.decode(errors='ignore')

            # Hapus escape ANSI
            ch_clean = re.sub(r'\x1B\[[0-?]*[ -/]*[@-~]', '', ch)
            buf += ch_clean

            # ⚡ Jika ketemu --More--, tekan Enter
            if "--More--" in buf:
                self.logger.debug("Detected --More--, sending Enter...")
                proc.stdin.write("\r\n")
                buf = buf.replace("--More--", "")

            # Cek apakah prompt muncul
            for p in prompts:
                if p in buf:
                    self.logger.debug(
                        f"Detected prompt '{p}' in buffer. Collected output:\n{buf.strip()}"
                    )
                    return buf



    async def write_cmd(self, proc, cmd):
        self.logger.info(f"Writing: {cmd}")
        proc.stdin.write(cmd + "\r\n")

    async def get_onus(self) -> Dict[str, Any]:
        self.logger.info(f"Connecting to HSGQ EPON OLT at {self.host}:{self.port}...")
        full_output = ""
        try:
            async with asyncssh.connect(
                self.host,
                port=self.port,
                known_hosts=None,
                username=self.ssh_user,
                password=self.ssh_pass,
                client_keys=None,
                connect_timeout=self.timeout
            ) as conn:
                self.logger.info("SSH login success. Starting manual CLI login...")

                proc = await conn.create_process(term_type='vt100')

                # Tahap 2: login CLI manual
                await self.wait_for_prompt(proc, "username:")
                await asyncio.sleep(0.5)
                await self.write_cmd(proc, self.cli_user)

                await self.wait_for_prompt(proc, "password:")
                await asyncio.sleep(0.5)
                await self.write_cmd(proc, self.cli_pass)

                await self.wait_for_prompt(proc, "MSNet_Fiber>")

                # Masuk enable → configure
                await self.write_cmd(proc, "enable")
                await self.wait_for_prompt(proc, "#")

                await self.write_cmd(proc, "configure")
                await self.wait_for_prompt(proc, "(config)#")

                # ⚡ Jalankan show onu-info all
                cmd = "show onu-info all"
                await self.write_cmd(proc, cmd)
                out = await self.wait_for_prompt(proc, "(config)#", timeout=20)
                full_output += out

        except Exception as e:
            self.logger.error(f"An error occurred: {e}")
            return {"error": str(e)}

        onus = self._parse_onu_info(full_output)
        return {"count": len(onus), "onus": onus}

    def _parse_onu_info(self, raw_output: str) -> List[Dict[str, Any]]:
        self.logger.debug("Parsing ONU info data...")
        parsed_onus = []
        text = raw_output.replace("\r", "").replace("--More--", "")

        pattern = re.compile(
            r"(\d+/\d+)\s+"                                 # PON/ONU
            r"([0-9a-fA-F:]{17})\s+"                         # MAC
            r"(Online|Offline)\s+"                           # Status
            r"(TRUE|FALSE)\s+"                               # Auth
            r"(TRUE|FALSE)\s+"                               # Cfg
            r"(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})\s+"     # Reg-time
            r"(\S+)\s+"                                      # ONU-Name
            r"(\S+)",                                        # ONU-Desc
            re.MULTILINE
        )

        for m in pattern.findall(text):
            mac_address = m[1].lower()
            parsed_onus.append({
                "identifier": mac_address,
                "pon_interface": m[0],
                "vendor_name": "hsgq",
                "details": {
                    "pon_interface": m[0],
                    "mac_address": mac_address,
                    "status": m[2],
                    "auth": m[3],
                    "cfg": m[4],
                    "reg_time": m[5],
                    "onu_name": m[6],
                    "onu_desc": m[7]
                }
            })

        self.logger.debug(f"Parsed {len(parsed_onus)} ONUs.")
        return parsed_onus
