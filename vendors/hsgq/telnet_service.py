from common.telnet_base import TelnetBase

class HsgqTelnetService(TelnetBase):
    def connect(self):
        print(f"Connecting to HSGQ Telnet at {self.host}:{self.port}")
        # Implementasi koneksi telnet spesifik untuk HSGQ di sini
        return True

    def execute_command(self, command):
        print(f"Executing on HSGQ: {command}")
        # Implementasi eksekusi command di sini
        return f"Output for {command}"

    def disconnect(self):
        print("Disconnecting from HSGQ Telnet")
        # Implementasi diskoneksi di sini
        pass
